# Global Codex Rules

## Windows sandbox

If command execution fails with `CreateProcessAsUserW failed: 1920`, treat it as a Windows sandbox/process-launch issue. Do not modify business code. Re-run the exact failed command with elevated permission and only re-run the failed command.

## Windows BAT / PowerShell JSON

When BAT-embedded PowerShell writes project JSON, use UTF-8 without BOM (for example `[System.IO.File]::WriteAllText(..., [System.Text.UTF8Encoding]::new($false))`). Windows PowerShell `Set-Content -Encoding UTF8` writes a BOM that breaks Python `json.loads(path.read_text(encoding="utf-8"))`.

## Local runtime assets

Keep local skills, local skill registry/settings, databases, imports, backups, logs, and sync bundles under `D:\YoubestarLocal` by default. The project root should keep program code and official registry only; `local.*` skills are loaded from `D:\YoubestarLocal\skills\local` with registry data in `D:\YoubestarLocal\registries`.

## Windows SQLite tests

When tests create SQLite files under a temporary `YOUBESTAR_LOCAL_HOME`, close every `sqlite3.Connection` explicitly. `with sqlite3.connect(...) as connection` commits or rolls back the transaction but does not close the file handle, so Windows cleanup can fail with `PermissionError: [WinError 32]`.

## LAN startup

Use `start.bat` for local service startup. It must run the real FastAPI entrypoint with `uvicorn server:app`, open the service URL instead of a raw file or `python -m http.server`, print local/LAN access info, and keep the console open for logs. LAN sharing is an official Management Config capability, not the default startup mode: persist it in `D:\YoubestarLocal\config\service.json`; when enabled, `start.bat` starts with `--host 0.0.0.0`, otherwise it starts with `--host 127.0.0.1`. If the configured port is already in use, the startup script should show the owning process and ask whether to stop it before continuing.

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

Youbestar's production direction is a self-owned local Agent Runtime. Do not reintroduce graph-framework side routes into the production code path.

New agent behavior should be designed around:

```text
AgentState -> AgentNode -> AgentRuntime -> AgentPolicy -> AgentCheckpoint
```

Do not keep adding one-off branches to `/chat` when the behavior belongs in the runtime.

Language understanding, query rewriting, synthesis, and answer completeness checks belong in the runtime node chain, not inside individual skills. Skills should provide observations; runtime nodes decide how to understand the user, improve tool parameters, synthesize evidence, and verify the final answer.

Runtime search behavior must follow finite planning, finite retry, and fast failure. Do not add unbounded Agent loops, unbounded Critic loops, or recursive search retries. Keep hard limits for search rounds, tool calls, and runtime.

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

Verified handling:

- For requests like "搜索 X 并告诉我结果" or "哪个地区", do not route to `official.open_browser` only. Add or use a query skill that returns structured data, and keep `official.open_browser` for explicit page-opening intent.
- Web/news queries must not hard-code a single search provider. Prefer an `auto` provider that tries mainland-accessible Chinese sources first and, when the current network environment allows it, also tries external search engines and information sources. Return the source name in structured rows.
- Search retry is capped: first search uses the original query, second search may use rewritten query candidates, and no third search is allowed.
- Stock quote requests must use the official `official.query_market_data` skill. It uses the lightweight Eastmoney two-step flow from `tools/stock_tool.py`: search stock by Chinese name/code, then fetch real-time quote by `secid`. Do not reintroduce AkShare wrappers, `function/api` stock side routes, the old `local.query_market_data` path, or browser scraping for normal quote lookups.
- Weather requests must use the official `official.query_weather` skill and local `tools/weather_tool.py` functions. Do not route weather, stock, or market quote requests to `official.web_query` or browser tools unless the user explicitly asks to search the web for related news/background.
- Excel preview/classification requests must use `official.preview_excel` to read every worksheet, show header-leading rows, detected headers plus the first 20 rows, classify the table type, map headers to Chinese-labeled standard fields, and surface field-catalog proposals before any database import. Preserve header-leading rows because factory/contact metadata is often above the detected header row. Follow-up chat after drag-and-drop upload must include the saved Excel path and preview summary in history so questions like “表格前几行的厂家信息是什么” can be answered from the uploaded file context. Unknown or ambiguous sheets must be reported as `unknown`/`ambiguous` instead of forced into quote/order/inventory categories. Field-catalog additions, alias additions, or meaning changes may be proposed by Youbestar, but must wait for a user confirmation popup or explicit confirmation before taking effect. Only route to `local.factory_quote` with `operation="import"` when the user explicitly asks to write/import an Excel that has been confirmed as a quotation table into the quote library.
- Excel quote imports must identify at least one business identity field before writing: `factory_name` or `brand`. If both are missing or ambiguous, return a confirmation-required result and do not write to SQLite. User-confirmed `factory_name`/`brand` values may be passed back into `local.factory_quote` import and then used for grouping, filtering, and product IDs.
- When reading quote Excel with `factory_name` or `brand` params, treat params as user-confirmed fallback identity only when the sheet does not expose that identity; do not overwrite a detected full factory/brand name just because the user used a short name as a query filter.
- Confirmed generic Excel mappings can be archived in `official.business_records` with `record_type="excel_table"`. This stores the confirmed mapping/table metadata in the shared business-records database; it does not replace quote-specific `local.factory_quote` imports. Business-records SQLite schema migration must add any missing legacy columns such as `content`, `fields_json`, and `search_text` before query/upsert.
- 1688 reference-product requests must use the official `official.reference_product` skill. Capture is lightweight: store SKU names, source SKU ids, cost/reference prices, stock, source URL, and remote image URLs in `D:\YoubestarLocal\cache\reference_products`; do not download images or write the business records database during capture. Generate match candidates first, require explicit confirmation before `confirm_bind` writes image URL fields to product records, and only download/cache images when `export_excel` needs embedded pictures. Keep the reference-product cache capped by cleanup policy, defaulting to 500MB.
- Dragging an Excel folder into the chat UI must recursively expand `DataTransfer.items` directory entries and upload every allowed Excel file through `/files/excel/preview`; keep a plain `DataTransfer.files` fallback for single-file drops and browsers without directory entries.
- Local fast-path parsing must preserve user parameters: weather phrases such as `未来三天` / `未来5天` / `未来7天` must set `days` accordingly, and stock phrases such as `贵州茅台最新股价` or `601601最新收盘价` must strip query modifiers before passing `symbol`.
- Chat mode is controlled by three independent switches: `allowChat`, `allowTools`, and `allowSkills`. If only `allowChat` is enabled, answer directly with the model and do not run tool/skill planning. `official.*` requires `allowTools`; `local.*` / `community.*` requires `allowSkills`.
- Full Python test verification uses `.\.venv\Scripts\python.exe -m unittest discover -s tests`; plain `python -m unittest` currently discovers 0 tests.

## Sensitive local files

Never upload or expose `youbestar.json`, `.env`, credentials, tokens, cookies, or `.git` internals.

## Memory management

Memory must be layered and conservative:

- Short-term memory may keep recent interaction context for immediate understanding and references.
- Temporary/chatty memory must not be promoted to long-term memory.
- Long-term memory is only for confirmed business facts such as customers, SKU, orders, ERP records, finance reports, and transactions.
- Model context for business operations must use only short-term memory plus confirmed long-term memory; never include unconfirmed candidates or casual temporary notes.
- Long-term memory should be isolated by business module to avoid ERP, private sales, Excel, and chat contexts polluting each other.

