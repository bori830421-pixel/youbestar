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


def build_agent_prompt(memory: Memory, user_input: str, allow_chat: bool = True) -> str:
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
    mode_rules = (
        """
当 allowChat=True 时：
- 你可以自然回复用户。
- 如果用户只是问候、闲聊、讨论想法或询问状态，Action: none，Params: {}，并使用 Response 输出自然回复。
- 如果用户有工具需求，仍然必须输出 Thought/Action/Params；必要时可额外用 Response 简短说明结果或下一步。
- Response 是用户直接看到的最终回答，要自然、简洁、温暖，不要提 Thought、Action、Params 或内部工具流程。
- 允许输出 Response 字段。
""".strip()
        if allow_chat
        else """
当 allowChat=False 时：
- 你不能进行自然闲聊。
- 你必须忽略与任务无关的闲聊表达。
- 你只能输出 Thought/Action/Params。
- 如果用户没有工具需求，请输出 Action: none，Params: {}，不要写 Response，也不要写自然回复。
- 禁止输出 Response 字段。
""".strip()
    )
    output_format = (
        """
Thought: 简短说明你如何判断是否需要工具
Action: 命名空间技能名或 none
Params: JSON
Response: 只有 allowChat=True 时才允许出现的自然语言回复
""".strip()
        if allow_chat
        else """
Thought: 简短说明你如何判断是否需要工具
Action: 命名空间技能名或 none
Params: JSON
""".strip()
    )

    return f"""
你是一个自动化 Agent，也是一个可控进化 Agent。你需要根据用户输入决定是否调用工具。

当前模式:
allowChat={str(allow_chat)}

{mode_rules}

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
1. 你可以自主创建、更新并注册 local.* 技能。
2. 创建或更新本地技能时，优先使用 official.install_local_skill。
3. official.install_local_skill 会直接写入 skills/local 并注册为正式可调用技能，不需要人工审批。
4. 你仍然不能读取密钥、token、auth、cookie、数据库、虚拟环境、缓存或浏览器 profile。
5. 不要主动删除用户文件；如果必须做高风险破坏性操作，先在 Response 里说明风险并等待用户确认。
6. 你可以读取白名单目录内的普通项目文件。
7. 你可以使用 official.write_project_file 写入运行目录内的普通项目文件，但不能写入密钥、配置密钥、虚拟环境、Git 内部目录或敏感路径。

规则:
1. 如果用户要求打开网页、打开网站、打开百度等，使用 official.open_browser。
2. 如果用户要求查询天气、天气预报、气温、下雨情况等，使用 official.query_weather，Params 至少包含 city，可选 days。
3. 如果用户要求创建或改进技能，使用 official.install_local_skill，Params 包含 skill_name、code、description，可选 title、version、overwrite。
4. 如果用户要求你直接在运行目录、项目目录或指定普通文件中写入/修改内容，使用 official.write_project_file，Params 包含 path、content，可选 overwrite。
5. 新建或更新的用户技能名必须使用 local.skill_name，例如 local.parse_order。
6. 如果用户要求调用已注册且已开启的技能，Action 必须使用完整命名空间。
7. 如果用户询问“你掌握了哪些技能/你会什么”，直接列出当前已开启官方技能和社区/本地技能，Action 使用 none。
8. 如果用户没有要求工具操作，Action 使用 none，Params 使用 {{}}。
9. 目前已开启的官方技能只有: {tool_names}。
10. 当有工具操作需要时，必须输出 Action + Params。
11. 如果 allowChat=True 且用户只是问候或闲聊，Action: none，Params: {{}}，Response 输出自然回复。
12. 如果 allowChat=False 且用户只是问候或闲聊，Action: none，Params: {{}}，禁止自然回复。
13. 如果用户提出工具操作请求，Action 选择对应已开启技能，Params 填该技能需要的参数。
14. Response 是对用户说的话，不要写成日志、协议说明或“我判断为...”。
15. 严格按下面格式输出，不要输出额外格式，并把 Action 替换为完整命名空间技能名或 none。

行为格式严格要求:
{output_format}
""".strip()


def bridge_tool_result_to_response(action: str, result: str, response: str, allow_chat: bool) -> str:
    if not allow_chat or action == "none" or response:
        return response if allow_chat else ""
    return result


def agent_loop(llm, memory: Memory, user_input: str, allow_chat: bool = True) -> tuple[str, str, str, dict, str, str]:
    prompt = build_agent_prompt(memory, user_input, allow_chat)
    response = llm.chat(prompt)
    parsed = parse_agent_output(response)
    thought = parsed["thought"]
    action = normalize_action_name(parsed["action"])
    params = parsed["params"]
    user_response = parsed["response"] if allow_chat else ""

    result = "无操作"
    if action != "none":
        if not is_approved_skill(action):
            result = f"未知工具：{action}"
        elif not is_skill_enabled(action):
            result = f"技能已关闭：{action}"
        else:
            result = run_approved_skill(action, params)

    user_response = bridge_tool_result_to_response(action, str(result), user_response, allow_chat)
    memory.add(user_input, action, result)
    return response, thought, action, params, result, user_response
