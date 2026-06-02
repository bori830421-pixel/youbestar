# Youbestar Agent

Youbestar Agent 是一个最小可运行、可扩展的本地 AI Agent 框架。

当前版本包含：

- FastAPI 后端
- 浏览器 HTML 前端
- 网页端模型配置保存
- OpenAI-compatible `/v1` 云端模型接口
- 受控技能系统
- 技能命名空间与注册表
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

- API 地址，例如 `https://api.openai.com/v1`
- 模型名
- API Key

配置会保存到：

```text
youbestar.json
```

注意：`youbestar.json` 可能包含 API Key，已经被 `.gitignore` 忽略，不要上传到 GitHub。

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

第一次上传空仓库时，双击：

```bat
github_upload.bat
```

后续拉取 GitHub 最新代码，双击：

```bat
github_sync.bat
```

注意：

- 空仓库第一次没有 `main` 分支，先上传，不要先同步。
- 如果 GitHub 要求登录，请先完成 Git Credential Manager 或 GitHub CLI 登录。
- `github_upload.bat` 会阻止已经被 Git 跟踪的 `youbestar.json` 继续上传。

## 测试

运行：

```bat
.venv\Scripts\python.exe -m unittest discover -s tests
```

当前测试覆盖：

- Agent 输出解析
- 命名空间技能注册
- 注册表加载并执行技能
- 未注册 Action 的处理

