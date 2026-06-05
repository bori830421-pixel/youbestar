# Global Codex Rules

## Windows sandbox

If command execution fails with `CreateProcessAsUserW failed: 1920`, treat it as a Windows sandbox/process-launch issue. Do not modify business code. Re-run the exact failed command with elevated permission and only re-run the failed command.

## Token-saving workflow

For non-trivial work:

1. Read project instructions first.
2. Define success criteria.
3. Inspect before editing.
4. Make surgical changes.
5. Verify with the smallest necessary command.
6. Update handoff notes.

## Communication

Do not claim completed unless verification was actually run.
Surface skipped tests, failed commands, and uncertainty.

# Youbestar Project Rules

## Agent architecture

Youbestar's production direction is a self-owned local Agent Runtime. LangGraph is only a reference and experiment path, not the core runtime dependency.

New agent behavior should be designed around:

```text
AgentState -> AgentNode -> AgentRuntime -> AgentPolicy -> AgentCheckpoint
```

Do not keep adding one-off branches to `/chat` when the behavior belongs in the runtime.

## Skill responsibility boundary

Skills must do business work and return structured results. Skills must not own final user-facing rendering.

Expected skill boundary:

```text
skill -> structured result
runtime/finalize -> core.ui_formatter
user -> formatted Markdown
```

Do not make each skill hand-write Markdown tables, emoji titles, or display-specific text. If a skill returns a dict/list/table-like result, the final response layer must format it through the shared formatter.

Preferred structured result shape:

```json
{
  "ok": true,
  "kind": "market_quote",
  "title": "证券行情查询结果",
  "columns": ["标的名称", "代码", "查询时间", "最新价"],
  "rows": [["香农芯创", "300475", "2026-06-05 16:14:36", 171.9]],
  "summary": {
    "标的名称": "香农芯创",
    "代码": "300475",
    "最新价": 171.9
  }
}
```

## Unified output formatting

All user-visible Agent replies must go through `core/ui_formatter.py`.

Formatter rules:

- Exactly one top-level title for each final reply.
- Complex replies should use second-level sections.
- Repeated data must be shown as a Markdown table.
- Key conclusions, quantities, amounts, product names, securities names, and securities codes should be bold.
- Tools and skills may return raw observations for debug fields, but the main `reply` must be user-facing Markdown.

## Unified network access

Network-enabled skills must not directly own encoding, timeout, User-Agent, retry, or JSON parsing behavior.

Add or reuse a shared network layer such as:

```text
core/http_client.py
```

Skills should call shared helpers such as:

```python
fetch_text(url)
fetch_json(url)
```

The shared client owns:

- request timeout
- browser-like User-Agent when needed
- HTTP charset detection
- UTF-8 / UTF-8-SIG / GB18030 / GBK fallback decoding
- JSON parsing from decoded text or raw bytes
- clear error messages

Do not hard-code "this API uses GBK" inside every skill. If a provider requires special handling, register that behavior in the shared client or a provider adapter, not in ad hoc skill rendering code.

## Capability grouping

Do not let skills grow as a flat pile of unrelated tiny tools.

Prefer capability domains:

```text
query_hub
market_data
weather_data
web_search
browser_headless
browser_desktop
```

User-facing routing can be unified, but provider implementations should remain separated internally.

Browser capability must distinguish:

- desktop/visible browser: for user-visible pages, login, manual inspection, screenshots.
- headless browser: for background search, scraping, extraction, and validation.

## Sensitive local files

Never upload or expose `youbestar.json`, `.env`, credentials, tokens, cookies, or `.git` internals.

