from dataclasses import dataclass
from typing import Any, Protocol

from agent_system.manager import is_approved_skill, run_approved_skill
from agent_system.skill_registry import is_skill_enabled
from core.agent_state import AgentState
from core.loop import build_agent_prompt, bridge_tool_result_to_response, normalize_action_name
from core.parser import parse_agent_output
from core.ui_formatter import format_agent_reply, format_error, observation_to_text
from memory.memory import Memory


FAILURE_MARKERS = ("失败", "错误", "未知工具", "技能已关闭", "error")


class AgentLLM(Protocol):
    def chat(self, prompt: str) -> str:
        ...


@dataclass
class AgentContext:
    llm: AgentLLM
    memory: Memory


def has_failed(observation: Any) -> bool:
    text = observation_to_text(observation)
    return any(marker.lower() in text.lower() for marker in FAILURE_MARKERS)


def prepare_node(state: AgentState, context: AgentContext) -> AgentState:
    state.visit("prepare")
    thread_memory = Memory()
    thread_memory.history = list(context.memory.history)
    prompt = build_agent_prompt(thread_memory, state.user_input, state.allow_chat)
    state.model_reply = context.llm.chat(prompt)
    parsed = parse_agent_output(state.model_reply)
    state.thought = parsed["thought"]
    state.action = normalize_action_name(parsed["action"])
    state.params = parsed["params"]
    state.response = parsed["response"] if state.allow_chat else ""
    return state


def execute_node(state: AgentState, context: AgentContext) -> AgentState:
    state.visit("execute")
    if state.action == "none":
        state.observation = "无操作"
        return state

    if not is_approved_skill(state.action):
        state.observation = f"未知工具：{state.action}"
    elif not is_skill_enabled(state.action):
        state.observation = f"技能已关闭：{state.action}"
    else:
        state.observation = run_approved_skill(state.action, state.params)
    return state


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
        state.reply = format_agent_reply(state.action, raw_reply, state.observation)
        state.response = state.reply
    else:
        state.reply = ""
        state.response = ""
    context.memory.add(state.user_input, state.action, observation_to_text(state.observation))
    return state
