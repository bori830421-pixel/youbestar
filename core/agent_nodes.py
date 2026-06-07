from dataclasses import dataclass
import json
import time
from typing import Any, Protocol

from agent_system.manager import is_approved_skill, run_approved_skill
from agent_system.skill_registry import is_skill_enabled
from core.agent_state import AgentState
from core.loop import build_agent_prompt, bridge_tool_result_to_response, normalize_action_name
from core.parser import parse_agent_output
from core.ui_formatter import format_agent_reply, format_error, format_plain_response, observation_to_text
from memory.memory import Memory


FAILURE_MARKERS = ("失败", "错误", "未知工具", "技能已关闭", "error")
MAX_QUERY = 5
MIN_SEARCH_RESULTS = 3
QUESTION_REQUIREMENT_PATTERNS = (
    ("是什么", ("是什么", "是啥", "介绍", "简介")),
    ("官方网址", ("官方网址", "官网", "官方网站", "网站地址")),
    ("地区", ("哪个地区", "哪里的", "所在地", "发生地")),
    ("时间", ("什么时候", "时间", "日期")),
    ("最新进展", ("最新", "进展", "现在怎么样", "后续")),
)


class AgentLLM(Protocol):
    def chat(self, prompt: str) -> str:
        ...


@dataclass
class AgentContext:
    llm: AgentLLM
    memory: Memory


def _extract_json_object(text: str) -> dict[str, Any]:
    clean_text = (text or "").strip()
    try:
        data = json.loads(clean_text)
    except json.JSONDecodeError:
        start = clean_text.find("{")
        end = clean_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        try:
            data = json.loads(clean_text[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return data if isinstance(data, dict) else {}


def build_understanding_prompt(state: AgentState) -> str:
    history_json = json.dumps(state.history[-6:], ensure_ascii=False, indent=2)
    return f"""
你是 Youbestar 的语言理解节点。请把用户原话解析成结构化意图，帮助后续 Agent 决定是否搜索、调用工具、逐项回答。

用户输入:
{state.user_input}

最近历史:
{history_json}

只输出 JSON 对象，不要 Markdown，不要解释。字段:
{{
  "task_type": "chat | web_research | tool_use | file_work | unknown",
  "subject": "用户主要询问对象，无法确定则为空字符串",
  "sub_questions": ["逐项列出用户要回答的问题"],
  "constraints": ["例如需要最新信息、中文回答、只要官网等"],
  "needs_fresh_info": true,
  "expected_output": "用户期望的回答形态",
  "query_hints": ["适合搜索的关键词，最多3条"]
}}
""".strip()


def understand_node(state: AgentState, context: AgentContext) -> AgentState:
    state.visit("understand")
    if not state.allow_chat:
        state.intent = {}
        return state
    parsed = _extract_json_object(context.llm.chat(build_understanding_prompt(state)))
    if parsed:
        state.intent = parsed
        sub_questions = parsed.get("sub_questions")
        if isinstance(sub_questions, list):
            state.plan = [str(item) for item in sub_questions if str(item).strip()]
    else:
        state.intent = {
            "task_type": "unknown",
            "subject": "",
            "sub_questions": [state.user_input],
            "constraints": [],
            "needs_fresh_info": False,
            "expected_output": "",
            "query_hints": [],
        }
    return state


def has_failed(observation: Any) -> bool:
    if isinstance(observation, dict):
        return observation.get("ok") is False
    text = observation_to_text(observation)
    return any(marker.lower() in text.lower() for marker in FAILURE_MARKERS)


def should_synthesize_answer(state: AgentState) -> bool:
    return (
        state.allow_chat
        and state.action == "official.web_query"
        and isinstance(state.observation, dict)
        and state.observation.get("ok") is True
    )


def infer_answer_requirements(user_input: str) -> list[str]:
    requirements: list[str] = []
    for label, patterns in QUESTION_REQUIREMENT_PATTERNS:
        if any(pattern in user_input for pattern in patterns):
            requirements.append(label)
    return requirements


def answer_requirements_for_state(state: AgentState) -> list[str]:
    requirements = infer_answer_requirements(state.user_input)
    sub_questions = state.intent.get("sub_questions") if isinstance(state.intent, dict) else None
    if isinstance(sub_questions, list):
        for item in sub_questions:
            clean_item = str(item).strip()
            if clean_item and clean_item not in requirements:
                requirements.append(clean_item)
    return requirements


def rewrite_query_node(state: AgentState, context: AgentContext) -> AgentState:
    state.visit("rewrite_query")
    if state.action != "official.web_query":
        return state

    original_query = str(state.params.get("query") or state.user_input).strip()
    hints = state.intent.get("query_hints") if isinstance(state.intent, dict) else None
    hint_values = [str(item).strip() for item in hints if str(item).strip()] if isinstance(hints, list) else []
    subject = str(state.intent.get("subject") or "").strip() if isinstance(state.intent, dict) else ""
    requirements = answer_requirements_for_state(state)

    candidates = [original_query, *hint_values]
    if subject and requirements:
        candidates.append(f"{subject} {' '.join(requirements)}")
    if subject:
        candidates.extend([f"{subject} latest model", f"{subject} official"])
    unique_candidates: list[str] = []
    for candidate in candidates:
        clean_candidate = str(candidate).strip()
        if clean_candidate and clean_candidate not in unique_candidates:
            unique_candidates.append(clean_candidate)

    state.params.setdefault("query", original_query)
    state.params["query_candidates"] = unique_candidates[:MAX_QUERY]
    state.params.setdefault("limit", 5)
    return state


def runtime_limit_reached(state: AgentState) -> str:
    if state.search_round >= state.max_search_round:
        return "search_limit_reached"
    if state.tool_call_count >= state.max_tool_call:
        return "tool_call_limit_reached"
    if state.runtime_started_at and time.monotonic() - state.runtime_started_at >= state.max_runtime_seconds:
        return "runtime_limit_reached"
    return ""


def should_prevent_tool_execution_for_runtime_limit(state: AgentState) -> bool:
    return state.action == "official.web_query"


def _web_rows(observation: Any) -> list[list[Any]]:
    if not isinstance(observation, dict):
        return []
    rows = observation.get("rows")
    return rows if isinstance(rows, list) else []


def assess_search_results(state: AgentState) -> dict[str, Any]:
    rows = _web_rows(state.observation)
    sources = []
    for row in rows:
        if isinstance(row, list) and row:
            sources.append(str(row[0]))
    unique_sources = sorted(set(source for source in sources if source and source != "-"))
    missing = state.answer_check.get("missing") if isinstance(state.answer_check, dict) else []
    if not isinstance(missing, list):
        missing = []

    reasons: list[str] = []
    if missing:
        reasons.append("missing_sub_questions")
    if len(rows) < MIN_SEARCH_RESULTS:
        reasons.append("too_few_results")
    if rows and len(unique_sources) <= 1:
        reasons.append("single_source")

    return {
        "retry": bool(reasons),
        "reasons": reasons,
        "result_count": len(rows),
        "source_count": len(unique_sources),
        "missing": missing,
    }


def partial_observation(reason: str) -> dict[str, Any]:
    return {
        "ok": True,
        "kind": "partial",
        "title": "部分查询结果",
        "summary": {
            "status": "partial",
            "reason": reason,
        },
        "columns": ["状态", "原因"],
        "rows": [["partial", reason]],
    }


def search_retry_node(state: AgentState, context: AgentContext) -> AgentState:
    state.visit("search_retry")
    if state.action != "official.web_query" or has_failed(state.observation):
        return state

    assessment = assess_search_results(state)
    state.search_assessment = assessment
    if not assessment.get("retry"):
        return state

    reason = runtime_limit_reached(state) if should_prevent_tool_execution_for_runtime_limit(state) else ""
    if reason:
        state.stop_reason = reason
        state.observation = partial_observation(reason)
        return state

    candidates = state.params.get("query_candidates")
    if not isinstance(candidates, list):
        candidates = []
    current_query = str(state.params.get("query") or "").strip()
    next_query = ""
    for candidate in candidates[:MAX_QUERY]:
        clean_candidate = str(candidate).strip()
        if clean_candidate and clean_candidate != current_query:
            next_query = clean_candidate
            break

    if not next_query:
        state.stop_reason = "search_limit_reached"
        state.observation = partial_observation(state.stop_reason)
        return state

    state.params["query"] = next_query
    run_action(state)
    second_assessment = assess_search_results(state)
    state.search_assessment = second_assessment
    if second_assessment.get("retry"):
        state.stop_reason = "search_limit_reached"
        state.observation = partial_observation(state.stop_reason)
    return state


def build_synthesis_prompt(state: AgentState) -> str:
    observation_json = json.dumps(state.observation, ensure_ascii=False, indent=2)
    requirements = answer_requirements_for_state(state)
    requirement_text = "\n".join(f"- {item}" for item in requirements) if requirements else "- 按用户原问题逐项提取需要回答的点"
    return f"""
你是 Youbestar 的结果综合节点。用户刚刚提出了一个需要联网搜索回答的问题。

用户问题:
{state.user_input}

必须覆盖的回答点:
{requirement_text}

搜索技能返回的结构化资料:
{observation_json}

请只根据上面的搜索资料回答用户，不要编造资料之外的事实。
要求:
- 先直接给出结论。
- 必须覆盖“必须覆盖的回答点”里的每一项；如果资料不足，就明确写“搜索结果中暂未找到...”。
- 如果用户一次问了多个问题，必须逐项回答，不要只回答其中一个。
- 再按信息分类整理，例如地区、人物/主体、时间、进展、证据来源等；没有的信息不要硬凑。
- 如果资料里出现多个地区，要区分它们的角色，例如买家所在地、商家所在地、事件发生地。
- 语气自然，面向用户，不要提 Thought、Action、Params、工具调用、内部流程。
- 输出 Markdown，但只要一段清晰答案即可，不要输出 JSON。
""".strip()


def synthesize_node(state: AgentState, context: AgentContext) -> AgentState:
    state.visit("synthesize")
    if should_synthesize_answer(state):
        state.response = context.llm.chat(build_synthesis_prompt(state)).strip()
        state.reflection = "已根据搜索结果综合回答。"
    return state


def build_answer_check_prompt(state: AgentState) -> str:
    requirements = answer_requirements_for_state(state)
    requirement_text = "\n".join(f"- {item}" for item in requirements) if requirements else "- 用户原问题"
    return f"""
你是 Youbestar 的回答自检节点。请检查最终回答是否覆盖用户问题。

用户问题:
{state.user_input}

必须覆盖的回答点:
{requirement_text}

当前回答:
{state.response}

只输出 JSON 对象，不要 Markdown。字段:
{{
  "ok": true,
  "missing": ["未覆盖的回答点"],
  "notes": "简短说明"
}}
""".strip()


def answer_check_node(state: AgentState, context: AgentContext) -> AgentState:
    state.visit("answer_check")
    if not state.allow_chat or not state.response:
        return state
    if state.action == "none" and not state.plan:
        return state

    check = _extract_json_object(context.llm.chat(build_answer_check_prompt(state)))
    if not check:
        return state
    state.answer_check = check

    missing = check.get("missing")
    if check.get("ok") is False and isinstance(missing, list) and missing:
        missing_text = "、".join(str(item) for item in missing if str(item).strip())
        if missing_text and missing_text not in state.response:
            state.response = f"{state.response}\n\n补充说明：搜索结果中暂未找到或当前回答尚未覆盖：{missing_text}。"
    return state


def prepare_node(state: AgentState, context: AgentContext) -> AgentState:
    state.visit("prepare")
    prompt = build_agent_prompt(context.memory, state.user_input, state.allow_chat)
    state.model_reply = context.llm.chat(prompt)
    parsed = parse_agent_output(state.model_reply)
    state.thought = parsed["thought"]
    state.action = normalize_action_name(parsed["action"])
    state.params = parsed["params"]
    state.response = parsed["response"] if state.allow_chat else ""
    return state


def run_action(state: AgentState) -> AgentState:
    if state.action == "none":
        state.observation = "无操作"
        return state

    reason = runtime_limit_reached(state) if should_prevent_tool_execution_for_runtime_limit(state) else ""
    if reason:
        state.stop_reason = reason
        state.observation = partial_observation(reason)
        return state

    if not is_approved_skill(state.action):
        state.observation = f"未知工具：{state.action}"
    elif not is_skill_enabled(state.action):
        state.observation = f"技能已关闭：{state.action}"
    else:
        state.tool_call_count += 1
        if state.action == "official.web_query":
            state.search_round += 1
        state.observation = run_approved_skill(state.action, state.params)
    return state


def execute_node(state: AgentState, context: AgentContext) -> AgentState:
    state.visit("execute")
    return run_action(state)


def reflect_node(state: AgentState, context: AgentContext) -> AgentState:
    state.visit("reflect")
    if not state.allow_chat:
        state.response = ""
        state.reflection = "任务优先模式，不生成自然回复。"
        return state

    if state.action == "none" and state.response:
        state.reflection = "已有自然回复，保留。"
        return state

    if state.action != "none" and has_failed(state.observation):
        state.response = format_error(observation_to_text(state.observation))
        state.reflection = "工具结果失败，已转成自然说明。"
    elif should_synthesize_answer(state):
        state.reflection = "搜索结果成功，等待综合节点生成答案。"
    elif state.action != "none":
        state.response = format_agent_reply(state.action, state.response, state.observation)
        state.reflection = "工具执行成功，已把结果作为回复。"
    else:
        state.response = "我在。你可以继续说。"
        state.reflection = "无工具且无自然回复，已提供兜底回复。"
    return state


def finalize_node(state: AgentState, context: AgentContext) -> AgentState:
    state.visit("finalize")
    raw_reply = bridge_tool_result_to_response(
        state.action,
        state.observation,
        observation_to_text(state.response),
        state.allow_chat,
    )
    if state.allow_chat:
        if should_synthesize_answer(state) and state.response:
            state.reply = format_plain_response(state.response, "查询结果")
        else:
            state.reply = format_agent_reply(state.action, raw_reply, state.observation)
        state.response = state.reply
    else:
        state.reply = ""
        state.response = ""
    context.memory.add(state.user_input, state.action, observation_to_text(state.observation))
    return state
