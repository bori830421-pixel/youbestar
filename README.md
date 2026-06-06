# Youbestar Agent

Youbestar Agent 是一个最小可运行、可扩展的本地 AI Agent 框架。

当前版本包含：

- FastAPI 后端
- 浏览器 HTML 前端
- 网页端模型配置保存
- 第三方 API 模型列表发现
- 闲聊模式 / 任务优先模式切换
- Youbestar 自研 Agent Runtime
- OpenAI-compatible `/v1` 云端模型接口
- 受控技能系统
- 技能命名空间与注册表
- 项目内普通文件写入技能
- 统一结构化 UI 输出格式层
- GitHub 同步/上传 bat 脚本

## 快速启动

双击：

```bat
start.bat
```

脚本会自动：

1. 检查并关闭 8000 端口旧服务
2. 创建 `.venv`
3. 安装 `requirements.txt`
4. 启动 FastAPI
5. 打开网页

访问地址：

```text
http://127.0.0.1:8000/
```

## 模型配置

首次打开网页后，需要填写：

- API 地址，例如 `https://api.deepseek.com/v1`
- 模型名
- API Key

配置会保存到：

```text
youbestar.json
```

注意：`youbestar.json` 可能包含 API Key，已经被 `.gitignore` 忽略，不要上传到 GitHub。

配置页填写 API 地址和 API Key 后，可以点击“获取模型”。Youbestar 后端会请求对应的 OpenAI-compatible `/models` 接口，例如：

```text
https://api.deepseek.com/v1
  -> https://api.deepseek.com/v1/models
```

拉取成功后，模型名输入框可以搜索和选择返回的模型。第三方接口不支持 `/models` 时，仍然可以手动填写模型名。

如果只填写供应商根地址，并且根 `/models` 返回 `404`，Youbestar 会尝试 `/v1/models`。成功后会自动把配置地址规范为对应的 `/v1` 基地址。

## 对话模式

聊天窗口提供一个“允许闲聊”开关：

- 开启：Chat On，模型可以输出自然语言回复，也可以调用技能。
- 关闭：Chat Off，任务优先，模型只能输出 `Thought / Action / Params`，不能输出自然闲聊。

前端请求 `/chat` 时会传：

```json
{
  "message": "你好",
  "allowChat": true
}
```

后端会根据 `allowChat` 改写 prompt，并返回结构化字段：

```json
{
  "thought": "...",
  "action": "official.open_browser",
  "params": {},
  "action_result": "无操作",
  "response": "你好！"
}
```

## Youbestar Agent Runtime

Youbestar Agent Runtime 的定位是：

```text
正式内核 / 本地可控 / 可长期扩展
```

第一版 Runtime 骨架已经拆分为：

```text
core/agent_state.py
core/agent_nodes.py
core/agent_runtime.py
core/agent_checkpoint.py
```

当前最小自研流程：

```text
prepare -> execute -> reflect -> finalize
```

`/chat` 当前默认使用自研 `AgentRuntime`。旧 `agent_loop` 仍作为兼容 fallback 保留，便于必要时快速回退。

## 结构化输出格式

Agent 面向用户的最终回复统一走：

```text
core/ui_formatter.py
```

当前 formatter 提供：

```text
format_order_result(data)
format_inventory(data)
format_error(msg)
format_agent_reply(action, response, action_result)
format_skill_result(result)
```

输出规范：

- 每次回复包含一个一级标题
- 复杂内容拆成二级模块
- 关键结论、数量、金额、商品名加粗
- 多条数据必须使用 Markdown 表格
- Emoji 只用于标题或少量提示，避免堆叠

天气查询等工具结果会由 Runtime / server 最终回复层转成结构化 Markdown，避免结果只藏在工具卡片里。

技能只负责业务执行和返回结构化结果，不负责最终 Markdown 渲染。新增技能应优先返回 `ok / kind / title / columns / rows / summary` 这类结构，由 `core/ui_formatter.py` 统一转成用户可见回复，避免每个技能重复写表格、Emoji 和标题格式。

自研 `AgentRuntime` 会保留技能返回的原始结构化结果，再交给 formatter。不要在执行节点里把技能结果直接 `str(dict)` 后返回给用户。

## 统一网络读取层

联网技能不要各自处理编码、请求头、超时和 JSON 解析。后续新增或改造联网能力时，应统一走共享网络层，例如：

```text
core/http_client.py
```

技能侧只调用：

```python
fetch_text(url)
fetch_json(url)
```

共享网络层负责：

- 超时和 User-Agent
- 从 HTTP Header 识别 charset
- 自动尝试 `utf-8-sig`、`utf-8`、`gb18030`、`gbk`
- JSON 解析和清晰错误提示

不要在每个证券、天气、搜索技能里手写“某接口用 GBK、某接口用 UTF-8”。特殊供应商差异应沉到统一网络层或 provider adapter。

当前已接入：

- `tools/weather_tool.py`
- `agent_system/skills/local/query_market_data.py`

## 能力归类规则

技能不应无限平铺增长。新增能力优先归入能力域：

```text
query_hub
market_data
weather_data
web_search
browser_headless
browser_desktop
```

浏览器能力必须拆成两类：桌面可见浏览器用于打开页面、登录和人工查看；无头浏览器用于后台搜索、抓取、提取和校验。

## 核心目录

```text
youbestar/
  server.py
  index.html
  requirements.txt
  start.bat
  github_sync.bat
  github_upload.bat
  core/
    agent_checkpoint.py
    agent_nodes.py
    agent_runtime.py
    agent_state.py
    http_client.py
    llm.py
    loop.py
    parser.py
    config.py
  tools/
    browser_tool.py
    evolution_tool.py
    file_access_tool.py
  memory/
    memory.py
  agent_system/
    manager.py
    server.py
    skill_registry.py
    file_access.py
    skills/
      official/
      community/
      local/
      registry.json
    sandbox/
    tests/
    approvals.json
```

## 技能系统

技能使用命名空间：

```text
official.open_browser
community.user123.parse_order
local.my_parse_order
```

技能不是简单文件，而是注册到：

```text
agent_system/skills/registry.json
```

注册表记录：

- 技能名
- 文件路径
- 版本
- 来源
- 作者
- 描述

Agent 调用技能时，会按 `Action` 查注册表，再加载对应模块并调用：

```python
run(params)
```

官方文件技能：

```text
official.list_files
official.read_file
official.write_project_file
official.web_query
local.query_market_data
```

`official.write_project_file` 可在项目白名单目录内写入普通文本或代码文件，参数示例：

```json
{
  "path": "docs/notes.md",
  "content": "hello",
  "overwrite": false
}
```

它仍会阻止写入敏感路径，例如 `.git`、`.venv`、`youbestar.json`、token、cookie、credential、secret 等命名的文件。

官方网页查询技能：

```text
official.web_query
```

用途：根据关键词自动尝试多个搜索源并返回结构化结果。默认国内可访问源优先；当当前网络环境允许时，会补充使用外网搜索引擎和信息源。适用于“帮我搜一下”“哪个地区”“这件事是什么情况”“最新有什么新出来的大模型”等需要直接给出答案的场景，不应退化成只打开百度页面或写死单一搜索源。

本地证券行情技能：

```text
local.query_market_data
```

用途：查询股票、指数行情数据。支持 `symbol`、可选 `date` 和 `fields`。最新行情走腾讯行情接口，历史日 K 走东方财富接口；网络读取统一走 `core.http_client.py`，避免中文名称乱码。技能返回结构化结果，由 `core.ui_formatter.py` 渲染成表格。

## 受控进化流程

模型不能直接修改正式技能。

正确流程：

```text
模型写代码 -> agent_system/sandbox/
模型写测试 -> agent_system/tests/
测试通过 -> 提交审批
人工批准 -> agent_system/skills/local/
写入 registry.json
Agent 才能调用
```

## GitHub 使用

仓库地址：

```text
https://github.com/bori830421-pixel/youbestar
```

把当前本地版本上传并覆盖 GitHub 时，双击：

```bat
github_upload.bat
```

从 GitHub 下载最新代码时，双击：

```bat
github_sync.bat
```

注意：

- 空仓库第一次没有 `main` 分支，先上传，不要先同步。
- `github_upload.bat` 以本地版本为准，会提交本地修改并使用 `--force-with-lease` 安全覆盖 GitHub；不会执行 pull。
- `github_sync.bat` 只下载，不会上传；发现未提交的本地修改会立即停止并保护文件。
- 下载同步使用 `--ff-only`，本地和远端历史分叉时会停止，不会自动改写历史。
- 如果 GitHub 要求登录，请先完成 Git Credential Manager 或 GitHub CLI 登录。
- `github_upload.bat` 会阻止已经被 Git 跟踪的 `youbestar.json` 继续上传。

## 测试

运行：

```bat
.venv\Scripts\python.exe -m unittest discover -s tests
```

当前测试覆盖：

- Agent 输出解析
- 可选 `Response` 解析
- 命名空间 Action 解析
- `allowChat` 模式 prompt
- 命名空间技能注册
- 注册表加载并执行技能
- 未注册 Action 的处理
