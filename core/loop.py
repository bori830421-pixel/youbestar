from core.parser import parse_agent_output
from agent_system.manager import is_approved_skill, load_skill_registry, run_approved_skill
from agent_system.skill_registry import (
    BUILTIN_SKILLS,
    canonical_skill_name,
    enabled_approved_skill_names,
    enabled_builtin_skill_names,
    is_skill_enabled,
)
from memory.memory import Memory


SELF_EVOLUTION_ACTIONS = {
    "official.install_local_skill",
    "official.list_files",
    "official.read_file",
    "official.request_skill_approval",
    "official.write_project_file",
    "official.write_skill",
    "official.write_skill_test",
}


EXCEL_CLASSIFICATION_GUIDE = """
Excel 通用表格处理分类系统:
- 定位：你不是只处理工厂报价表，而是处理报价表、订单表、库存表、客户表、采购表、财务表、物流表、商品资料表等各种 Excel。
- 固定流程：先用 official.preview_excel 读取所有工作表；展示表头前几行、检测到的表头和前 20 行；再识别表格类型、映射中文标准字段、标出未识别字段和待确认字段目录建议。
- 分类规则：不能把 unknown/ambiguous 强行拼成报价表、订单表或库存表；分类错误时应让用户通过修正分类/修正字段反馈来调整，重新预览同类表头时再应用已确认反馈。
- 字段目录规则：标准字段必须显示中文名；字段目录新增、别名新增或含义修改只能提出建议，必须等待用户弹窗或明确确认后才生效。
- 写库规则：预览阶段绝不写数据库。只有用户明确要求归档/写入，并且表格类型、字段映射和关键身份字段满足要求时，才允许进入对应写库技能。
- 身份门禁：写入报价资料库前必须至少识别或由用户确认 factory_name 工厂名称、brand 品牌二者之一；二者都未识别或不确定时，必须停止写入并询问用户确认。
- 禁止误读：禁止把文件名、普通标题、第一行泛称随便当工厂名称；“品牌价”是 cost_unit_price 成本单价，不是 brand 品牌；未识别字段必须标为未识别，不能乱猜。
- 示例：表头前几行出现“吉贵（原中意）玩具厂报价表”可作为 factory_name；只有“产品报价表”且无厂家/品牌时不得写库；有“品牌”列且值为“星河牌”可作为 brand；“品牌价”映射为成本单价。
""".strip()


def normalize_action_name(action: str) -> str:
    if action == "none":
        return "none"
    try:
        return canonical_skill_name(action)
    except Exception:
        return action


def _format_registered_skill_lines(skill_names: list[str]) -> str:
    if not skill_names:
        return "暂无"
    registry = load_skill_registry()
    lines = []
    for name in skill_names:
        record = registry.get(name, {})
        title = str(record.get("title") or name).strip()
        description = str(record.get("description") or "已注册技能。").strip()
        lines.append(f"- {name}: {title}。{description}")
    return "\n".join(lines)


def build_agent_prompt(
    memory: Memory,
    user_input: str,
    allow_chat: bool = True,
    allow_tools: bool = True,
    allow_skills: bool = True,
    allow_self_evolution: bool = False,
) -> str:
    enabled_tools = enabled_builtin_skill_names() if allow_tools else []
    tool_names = ", ".join(enabled_tools) if enabled_tools else "暂无"
    disabled_tools = [name for name in BUILTIN_SKILLS if name not in enabled_tools]
    disabled_tool_text = ", ".join(disabled_tools) if disabled_tools else "暂无"
    enabled_tool_lines = "\n".join(
        f"- {name}: {BUILTIN_SKILLS[name]['description']}" for name in enabled_tools
    ) or "暂无"
    registered_skills = enabled_approved_skill_names() if allow_skills else []
    registered_skill_text = _format_registered_skill_lines(registered_skills)
    history = memory.get_summary() or "暂无"
    business_memory = memory.get_business_summary() or "暂无"
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
allowTools={str(allow_tools)}
allowSkills={str(allow_skills)}
allowSelfEvolution={str(allow_self_evolution)}

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
- allowTools=False 时不要选择 official.* Action。
- allowSkills=False 时不要选择 local.* 或 community.* Action。
- 只有注册到 agent_system/skills/registry.json 的技能才是正式可调用技能。

历史信息:
{history}

已确认长期业务记忆:
{business_memory}

记忆使用规则:
- 只能使用短期历史和上面的已确认长期业务记忆。
- 不要使用未确认候选记忆、临时闲聊记忆或猜测信息来执行 ERP、订单、SKU、客户、财务相关任务。
- 如果长期记忆不足，明确说明需要用户补充或确认，不要自动固化。

权限规则:
1. allowSelfEvolution=False 时，禁止选择 official.list_files、official.read_file、official.write_project_file、official.write_skill、official.write_skill_test、official.request_skill_approval、official.install_local_skill 等读取/修改自身项目或技能的 Action。
2. allowSelfEvolution=True 时，你可以读取白名单目录内的普通项目代码文件，也可以自主创建、更新并注册 local.* 技能。
3. allowSelfEvolution=True 且用户要求创建或更新本地技能时，优先使用 official.install_local_skill。
4. official.install_local_skill 会直接写入 skills/local 并注册为正式可调用技能，不需要人工审批。
5. 即使 allowSelfEvolution=True，也仍然不能读取或写入密钥、token、auth、cookie、数据库、虚拟环境、缓存、浏览器 profile、.git 内部目录、youbestar.json 或 .env。
6. 不要主动删除用户文件；如果必须做高风险破坏性操作，先在 Response 里说明风险并等待用户确认。
7. allowSelfEvolution=True 时，你可以使用 official.write_project_file 写入运行目录内的普通项目文件，但不能写入敏感路径或受保护文件。
8. 新建或更新联网技能时，必须复用 core.http_client 的 fetch_text/fetch_json，不要在技能里各自处理编码、超时、请求头或 JSON 解析。
9. 新建或更新技能时，技能只返回结构化数据，不要手写最终 Markdown 渲染；用户可见展示由 core.ui_formatter 统一处理。

{EXCEL_CLASSIFICATION_GUIDE}

规则:
1. 如果用户明确要求打开网页、打开网站、打开百度、在浏览器中打开链接等，使用 official.open_browser。
2. 如果用户要求查询股票、证券行情、股价、涨跌幅，或输入类似“中国太保”“贵州茅台”这类股票中文名并询问价格/行情，直接使用 official.query_market_data，Params 至少包含 symbol，可以是中文名称或股票代码。不要为股票查询调用浏览器、网页搜索、模型自拼 API URL 或 function/api 扩展接口。
3. 如果用户要求查询天气、天气预报、气温、下雨情况等，直接使用 official.query_weather，Params 至少包含 city，可选 days。不要为天气查询调用浏览器、网页搜索或模型自拼 API URL。
4. 如果用户要求联网搜索、查询某个事件是什么、哪个地区、帮我搜并告诉我结果、最新热点、最近发布、新出来的大模型/产品/政策/新闻等，优先使用 official.web_query，Params 至少包含 query，可选 limit。但股票、天气、股市行情等已有本地函数工具的外部数据查询必须优先走对应工具，禁止退化成网页搜索。不要指定单一搜索源，除非用户明确要求；网络环境允许时，搜索工具会自动尝试外网搜索引擎和信息源。
5. 如果用户要求读取、预览、检查、分析、识别、分类 Excel 文件，或要求先看有哪些表头、表头前几行、前 20 行、厂家信息、其他工作表，使用 official.preview_excel。Params 包含 path 或 source_path，可选 filename、preview_rows，默认 20；如果 source_path 是文件夹且用户给了文件名，必须把文件名放入 filename 或直接拼成 workbook_path。必须按“Excel 通用表格处理分类系统”的固定流程回复；不要在预览阶段写入资料库。
6. 如果用户询问工厂报价、货号资料、产品尺寸、包装尺寸、外箱尺寸、箱规尺寸、装箱数量、箱毛重/箱净重、单品毛重/单品净重、快递包装重量、成本价、不同数量报价、含税/含运费、业务员、业务联系人、业务电话、联系电话、SKU图、主图、实拍图或 1688/相册图片绑定，且 local.factory_quote 已开启，使用 local.factory_quote。Params 可包含 factory_name、brand、sku、quantity、margin_rate、tax_rate、include_tax、include_freight、freight_fee、source_path、image_url、source_url、operation、image_type、product_size_cm、package_size_cm、carton_size_cm、single_net_weight_g、single_gross_weight_g、shipping_packaged_weight_g。只有用户明确要求从已确认为报价表的 Excel 写入/导入报价资料库时，operation 使用 import，并提供 source_path 或 workbook_path；写库前必须执行“身份门禁”，二者都未识别时不得直接写入，必须让用户确认后再导入；用户只要求先读取、预览、识别、分类、查看表头或前 20 行时，使用 official.preview_excel 而不是 local.factory_quote。用户只询问业务员/业务联系人/业务电话/联系电话时 operation 使用 contact，并尽量提供 factory_name；用户明确说“绑定图片/写入图片/你绑定”时 operation 使用 bind_image，并提供 factory_name、sku、image_url 或 image_id；默认图片绑定为 image_type="sku_image"，用户明确说“实拍图/实拍照片”时使用 image_type="real_photo"，用户明确说“SKU图/主图”时使用 image_type="sku_image"；用户明确说“产品尺寸/包装尺寸/包装规格/箱规尺寸填错、要修改、要写入资料库、调换过来”时 operation 使用 update_specs，并传 product_size_cm、package_size_cm 或 carton_size_cm；用户明确说“单品净重/单品毛重/包装重量/快递包装重量是 X 克，要写入/记住/保存”时 operation 使用 update_weight，并传对应重量字段；只想先暂存图片候选时才使用 operation=image_candidate。报价资料里的毛重/净重默认是箱重，单品重量由箱重 ÷ 装箱数 × 1000 换算为克，已有手动写入重量时优先使用手动值；尺寸默认 cm，价格默认人民币元且展示两位小数。
6.5. 如果用户要求查询、录入、保存、更新或维护共享办公资料库、资料库、办公资料、业务资料、客户资料、产品资料、订单资料、采购资料、库存资料、财务资料、物流资料，或说“查记录/查资料/新增记录/修改资料/保存到资料库/写入资料库/更新资料/列出资料类型”，使用 official.business_records。Params 包含 operation，可为 query、upsert、list_types 或 status；写入时包含 record_type、fields、title、content、tags、source、actor，查询时包含 record_type、query、business_key、filters、limit。不要把 Excel 预览、字段确认或工厂报价专用导入抢到 official.business_records；Excel 读取/识别仍优先 official.preview_excel，工厂报价库仍优先 local.factory_quote。
6.6. 如果用户发送 1688 商品详情链接，或要求读取/采集参考商品、抓 SKU 名称、SKU 图片链接、SKU 价格、参考商品图片关联、和资料库生成候选、确认绑定图片 URL、导出带图 SKU/客户报价 Excel，使用 official.reference_product。Params 包含 operation，可为 capture、match、confirm_bind、export_excel、cache_status 或 cleanup_cache；capture 只轻读取 SKU、价格、库存、图片 URL 和来源链接，不下载图片、不写资料库；match 只生成候选；confirm_bind 必须在用户明确确认后传 confirmed=true 才写入资料库；export_excel 只有需要图片时才下载图片到临时缓存并嵌入 Excel。用户只发链接但没说明下一步时，先 operation="capture"，读完后询问是生成候选、导出内部 Excel 还是导出客户报价 Excel。客户报价可传 margin_rate 或 margin_percent，价格默认保留 decimal_places=2。
7. 如果用户要求创建或改进技能，使用 official.install_local_skill，Params 包含 skill_name、code、description，可选 title、version、overwrite。
8. 如果用户要求你直接在运行目录、项目目录或指定普通文件中写入/修改内容，使用 official.write_project_file，Params 包含 path、content，可选 overwrite。
9. 新建或更新的用户技能名必须使用 local.skill_name，例如 local.parse_order。
10. 如果用户要求调用已注册且已开启的技能，Action 必须使用完整命名空间。
11. 如果用户询问“你掌握了哪些技能/你会什么”，直接列出当前已开启官方技能和社区/本地技能，Action 使用 none。
12. 如果用户没有要求工具操作，Action 使用 none，Params 使用 {{}}。
13. 目前已开启的官方技能只有: {tool_names}。
14. 当有工具操作需要时，必须输出 Action + Params。
15. 如果 allowChat=True 且用户只是问候或闲聊，Action: none，Params: {{}}，Response 输出自然回复。
16. 如果 allowChat=False 且用户只是问候或闲聊，Action: none，Params: {{}}，禁止自然回复。
17. 如果用户提出工具操作请求，Action 选择对应已开启技能，Params 填该技能需要的参数。
18. Response 是对用户说的话，不要写成日志、协议说明或“我判断为...”。
19. 创建查询类技能时，优先按能力域归类，例如 market_data、weather_data、web_search、browser_headless、browser_desktop，不要让同类能力无限平铺。
20. 对“打开百度搜索某关键词”这类请求，如果用户最终目的明显是获取答案而不是只看网页，优先使用 official.web_query；只有用户明确强调“打开浏览器”时才使用 official.open_browser。
21. 对“最新有什么新出来的大模型”这类没有具体名称但需要时效信息的问题，也必须使用 official.web_query，并把用户原话或补全后的中文关键词作为 query。
22. 严格按下面格式输出，不要输出额外格式，并把 Action 替换为完整命名空间技能名或 none。

行为格式严格要求:
{output_format}
""".strip()


def bridge_tool_result_to_response(action: str, result: str, response: str, allow_chat: bool) -> str:
    if not allow_chat or action == "none" or response:
        return response if allow_chat else ""
    return result


def agent_loop(
    llm,
    memory: Memory,
    user_input: str,
    allow_chat: bool = True,
    allow_tools: bool = True,
    allow_skills: bool = True,
    allow_self_evolution: bool = False,
) -> tuple[str, str, str, dict, str, str]:
    prompt = build_agent_prompt(
        memory,
        user_input,
        allow_chat,
        allow_tools=allow_tools,
        allow_skills=allow_skills,
        allow_self_evolution=allow_self_evolution,
    )
    response = llm.chat(prompt)
    parsed = parse_agent_output(response)
    thought = parsed["thought"]
    action = normalize_action_name(parsed["action"])
    params = parsed["params"]
    user_response = parsed["response"] if allow_chat else ""

    result = "无操作"
    if action != "none":
        if action.startswith("official.") and not allow_tools:
            result = f"工具调用未开启：{action}"
        elif action in SELF_EVOLUTION_ACTIONS and not allow_self_evolution:
            result = f"自我进化未开启：{action}"
        elif action.startswith(("local.", "community.")) and not allow_skills:
            result = f"技能调用未开启：{action}"
        elif not is_approved_skill(action):
            result = f"未知工具：{action}"
        elif not is_skill_enabled(action):
            result = f"技能已关闭：{action}"
        else:
            result = run_approved_skill(action, params)

    user_response = bridge_tool_result_to_response(action, str(result), user_response, allow_chat)
    memory.add(user_input, action, result)
    return response, thought, action, params, result, user_response
