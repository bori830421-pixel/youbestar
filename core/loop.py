from core.parser import parse_agent_output
from agent_system.manager import is_approved_skill, run_approved_skill
from agent_system.skill_registry import (
    BUILTIN_SKILLS,
    canonical_skill_name,
    enabled_approved_skill_names,
    enabled_builtin_skill_names,
    is_skill_enabled,
)
from memory.memory import Memory


def normalize_action_name(action: str) -> str:
    if action == "none":
        return "none"
    try:
        return canonical_skill_name(action)
    except Exception:
        return action


def build_agent_prompt(memory: Memory, user_input: str) -> str:
    enabled_tools = enabled_builtin_skill_names()
    tool_names = ", ".join(enabled_tools) if enabled_tools else "暂无"
    disabled_tools = [name for name in BUILTIN_SKILLS if name not in enabled_tools]
    disabled_tool_text = ", ".join(disabled_tools) if disabled_tools else "暂无"
    enabled_tool_lines = "\n".join(
        f"- {name}: {BUILTIN_SKILLS[name]['description']}" for name in enabled_tools
    ) or "暂无"
    registered_skills = enabled_approved_skill_names()
    registered_skill_text = ", ".join(registered_skills) if registered_skills else "暂无"
    history = memory.get_summary() or "暂无"

    return f"""
你是一个自动化 Agent，也是一个可控进化 Agent。你需要根据用户输入决定是否调用工具。

用户输入:
{user_input}

当前掌握并已开启的基础技能:
{enabled_tool_lines}

已关闭的官方技能:
{disabled_tool_text}

已注册并已开启的社区/本地技能:
{registered_skill_text}

说明:
- 所有技能都必须使用命名空间，例如 official.open_browser、community.user123.parse_order、local.my_parse_order。
- official 是官方技能，community 是社区共享技能，local 是用户本地技能。
- 官方技能也是你已经掌握的技能，不要把“本地技能为空”理解为“没有技能”。
- 只有注册到 agent_system/skills/registry.json 的技能才是正式可调用技能。

历史信息:
{history}

权限规则:
1. 你可以创建新的技能，但只能写入 sandbox。
2. 你可以提供测试用例，并提交审批请求。
3. 你不能修改已有 skills，不能操作系统文件，不能调用 ERP/微信，不能删除文件。
4. 未批准技能不能被当作正式工具调用。
5. 所有技能必须输入输出清晰，测试通过后才能申请审批。
6. 你可以读取白名单目录内的普通项目文件，但不能读取密钥、token、auth、cookie、数据库、虚拟环境、缓存或浏览器 profile。

规则:
1. 如果用户要求打开网页、打开网站、打开百度等，使用 official.open_browser。
2. 如果用户要求创建新技能，按顺序使用 official.write_skill、official.write_skill_test、official.request_skill_approval。
3. 新建并提交审批的用户技能名必须使用 local.skill_name，例如 local.parse_order。
4. 如果用户要求调用已注册且已开启的技能，Action 必须使用完整命名空间。
5. 如果用户询问“你掌握了哪些技能/你会什么”，直接列出当前已开启官方技能和社区/本地技能，Action 使用 none。
6. 如果用户没有要求工具操作，Action 使用 none，Params 使用 {{}}。
7. 目前已开启的官方技能只有: {tool_names}。
8. 当有工具操作需要时，必须输出 Action + Params。
9. 如果用户只是问候或闲聊，Action: none，Params: {{}}。
10. 如果用户提出工具操作请求，Action 选择对应已开启技能，Params 填该技能需要的参数。
11. 严格按下面格式输出，不要输出额外格式，并把 Action 替换为完整命名空间技能名或 none。

Thought: 简短说明你如何判断是否需要工具
Action: 命名空间技能名或 none
Params: JSON
""".strip()


def agent_loop(llm, memory: Memory, user_input: str) -> tuple[str, str, str, dict, str]:
    prompt = build_agent_prompt(memory, user_input)
    response = llm.chat(prompt)
    parsed = parse_agent_output(response)
    thought = parsed["thought"]
    action = normalize_action_name(parsed["action"])
    params = parsed["params"]

    result = "无操作"
    if action != "none":
        if not is_approved_skill(action):
            result = f"未知工具：{action}"
        elif not is_skill_enabled(action):
            result = f"技能已关闭：{action}"
        else:
            result = run_approved_skill(action, params)

    memory.add(user_input, action, result)
    return response, thought, action, params, result
