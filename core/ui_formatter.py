import re
from typing import Any


WEATHER_LINE_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})：最高 (?P<max>[-\d.]+°C)，最低 (?P<min>[-\d.]+°C)，降雨概率 (?P<rain>[-\d.]+%)$"
)


def bold(value: Any) -> str:
    return f"**{value}**"


def _is_markdown_image(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"!\[[^\]]*\]\([^)]+\)", value.strip()) is not None


def _bold_for_display(value: Any) -> Any:
    return value if _is_markdown_image(value) else bold(value)


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    header_line = "| " + " | ".join(headers) + " |"
    divider = "| " + " | ".join(["---"] * len(headers)) + " |"
    row_lines = ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join([header_line, divider, *row_lines])


def observation_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if isinstance(value.get("content"), str):
            return value["content"]
        if isinstance(value.get("message"), str):
            return value["message"]
        if isinstance(value.get("error"), str):
            return value["error"]
    return str(value)


def format_plain_response(text: str, title: str = "回复") -> str:
    clean_text = (text or "").strip() or "我在。你可以继续说。"
    return f"# ✅ {title}\n\n## 🔍 结果\n\n{clean_text}"


def format_error(msg: str) -> str:
    clean_msg = (msg or "未知错误").strip()
    return (
        "# ❌ 执行失败\n\n"
        "## ⚠️ 失败原因\n\n"
        f"这次执行没有成功：{bold(clean_msg)}\n\n"
        "## 🔍 建议\n\n"
        "你可以换个说法，或者让我先创建、启用对应技能。"
    )


def format_order_result(data: dict[str, Any]) -> str:
    items = data.get("items", [])
    rows = [
        [
            bold(item.get("name", "")),
            bold(item.get("quantity", item.get("qty", ""))),
            item.get("unit_price", item.get("price", "")),
            bold(item.get("subtotal", "")),
        ]
        for item in items
    ]
    table = markdown_table(["商品", "数量", "单价", "小计"], rows) if rows else "暂无订单明细。"
    total = data.get("total", data.get("amount", ""))
    return (
        "# 🛒 订单计算结果\n\n"
        "## 📊 订单明细\n\n"
        f"{table}\n\n"
        "## 💰 金额汇总\n\n"
        f"应收金额：{bold(total)}"
    )


def format_inventory(data: dict[str, Any]) -> str:
    items = data.get("items", [])
    rows = [
        [
            bold(item.get("name", "")),
            bold(item.get("stock", item.get("quantity", ""))),
            item.get("status", "正常"),
        ]
        for item in items
    ]
    table = markdown_table(["商品", "库存", "状态"], rows) if rows else "暂无库存明细。"
    return (
        "# 📦 库存查询结果\n\n"
        "## 📊 库存明细\n\n"
        f"{table}\n\n"
        "## ✅ 关键结论\n\n"
        "库存信息已整理完成。"
    )


def parse_weather_result(text: str) -> tuple[str, list[list[str]]] | None:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not lines or "天气预报" not in lines[0]:
        return None

    title = lines[0]
    rows: list[list[str]] = []
    for line in lines[1:]:
        match = WEATHER_LINE_RE.match(line)
        if not match:
            continue
        rows.append(
            [
                match.group("date"),
                bold(match.group("max")),
                bold(match.group("min")),
                bold(match.group("rain")),
            ]
        )
    return title, rows


def format_weather_result(text: str) -> str:
    parsed = parse_weather_result(text)
    if not parsed:
        return format_plain_response(text, "查询结果")

    title, rows = parsed
    if not rows:
        return format_plain_response(text, "查询结果")
    table = markdown_table(["日期", "最高温", "最低温", "降雨概率"], rows) if rows else "暂无天气明细。"
    day_count = len(rows)
    return (
        f"# 🔍 {title}\n\n"
        "## 📊 天气明细\n\n"
        f"{table}\n\n"
        "## ✅ 关键结论\n\n"
        f"已查询到未来 {bold(str(day_count) + '天')} 的天气数据，建议根据降雨和气温安排出行。"
    )


def _emphasize_table_rows(rows: list[list[Any]]) -> list[list[Any]]:
    return [[_bold_for_display(cell) if index in (0, 1) and cell not in ("", None, "-") else cell for index, cell in enumerate(row)] for row in rows]


def format_skill_result(result: Any) -> str:
    if isinstance(result, dict):
        if result.get("ok") is False:
            return format_error(observation_to_text(result))

        title = str(result.get("title") or "执行结果")
        if result.get("kind") == "excel_preview":
            return format_excel_preview_result(result)

        content = result.get("content")
        if isinstance(content, str) and content.strip():
            return f"# ✅ {title}\n\n## 📊 结果明细\n\n{content.strip()}"

        columns = result.get("columns")
        rows = result.get("rows")
        if isinstance(columns, list) and isinstance(rows, list):
            clean_columns = [str(column) for column in columns]
            clean_rows = [list(row) if isinstance(row, (list, tuple)) else [row] for row in rows]
            table = markdown_table(clean_columns, _emphasize_table_rows(clean_rows)) if clean_rows else "暂无明细数据。"
            summary = result.get("summary")
            summary_lines: list[str] = []
            if isinstance(summary, dict):
                for key, value in summary.items():
                    summary_lines.append(f"{key}：{_bold_for_display(value)}")
            summary_block = "\n".join(summary_lines) if summary_lines else "已整理完成。"
            return (
                f"# 🔍 {title}\n\n"
                "## 📊 数据明细\n\n"
                f"{table}\n\n"
                "## ✅ 关键结论\n\n"
                f"{summary_block}"
            )

    if isinstance(result, list):
        rows = [row if isinstance(row, list) else [row] for row in result]
        table = markdown_table(["结果"], rows) if rows else "暂无结果。"
        return f"# 🔍 查询结果\n\n## 📊 数据明细\n\n{table}"

    return format_plain_response(observation_to_text(result), "执行结果")


def format_excel_preview_result(result: dict[str, Any]) -> str:
    title = str(result.get("title") or "Excel 读取预览")
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    sheets = data.get("sheets") if isinstance(data, dict) else []
    saved_path = data.get("saved_path") if isinstance(data, dict) else ""
    file_name = data.get("file_name") if isinstance(data, dict) else ""
    classification_summary = data.get("classification_summary") if isinstance(data, dict) else {}
    status_counts = classification_summary.get("status_counts") if isinstance(classification_summary, dict) else {}

    sections: list[str] = [f"# 🔍 {title}"]
    sections.append(
        "## ✅ 关键结论\n\n"
        f"文件：{bold(file_name or '-')}\n\n"
        f"保存路径：{bold(saved_path or '-')}\n\n"
        f"工作表数：{bold(len(sheets) if isinstance(sheets, list) else 0)}\n\n"
        f"已识别：{bold(status_counts.get('recognized', 0) if isinstance(status_counts, dict) else 0)}；"
        f"部分识别：{bold(status_counts.get('partial', 0) if isinstance(status_counts, dict) else 0)}；"
        f"类型不明确：{bold(status_counts.get('ambiguous', 0) if isinstance(status_counts, dict) else 0)}；"
        f"未识别：{bold(status_counts.get('unknown', 0) if isinstance(status_counts, dict) else 0)}"
    )

    if isinstance(sheets, list):
        for sheet in sheets:
            if not isinstance(sheet, dict):
                continue
            sheet_name = str(sheet.get("name") or "未命名工作表")
            headers = [str(header) for header in sheet.get("headers") or []]
            rows = sheet.get("rows") if isinstance(sheet.get("rows"), list) else []
            header_text = "、".join(bold(header) for header in headers) if headers else "未识别到表头"
            preview_rows = [list(row) if isinstance(row, (list, tuple)) else [row] for row in rows]
            table = markdown_table(headers, preview_rows) if headers and preview_rows else "暂无可预览数据行。"
            classification = sheet.get("classification") if isinstance(sheet.get("classification"), dict) else {}
            status_text = _excel_classification_status_text(classification)
            reason_text = _excel_classification_reasons_text(classification)
            mapping_text = _excel_field_mapping_table(classification)
            proposal_text = _excel_change_proposal_table(classification)
            sections.append(
                f"## 📊 工作表：{sheet_name}\n\n"
                f"表头行：{bold(sheet.get('header_row', '-'))}\n\n"
                f"{status_text}\n\n"
                f"{reason_text}\n\n"
                f"{mapping_text}\n\n"
                f"{proposal_text}\n\n"
                f"读取到的表头：{header_text}\n\n"
                f"{table}"
            )

    return "\n\n".join(sections)


def _excel_classification_status_text(classification: dict[str, Any]) -> str:
    if not classification:
        return "识别状态：**未识别**"
    status_labels = {
        "recognized": "已识别",
        "partial": "部分识别，待确认",
        "ambiguous": "类型不明确，待选择",
        "unknown": "未识别",
    }
    status = str(classification.get("status") or "unknown")
    category_label = str(classification.get("category_label") or "未识别")
    confidence = classification.get("confidence", 0)
    try:
        confidence_text = f"{float(confidence) * 100:.0f}%"
    except (TypeError, ValueError):
        confidence_text = "0%"
    return f"识别状态：{bold(status_labels.get(status, status))}；表格类型：{bold(category_label)}；置信度：{bold(confidence_text)}"


def _excel_classification_reasons_text(classification: dict[str, Any]) -> str:
    reasons = classification.get("reasons") if isinstance(classification, dict) else []
    if not isinstance(reasons, list) or not reasons:
        return "识别说明：暂无。"
    return "识别说明：" + "；".join(str(reason) for reason in reasons)


def _excel_field_mapping_table(classification: dict[str, Any]) -> str:
    mappings = classification.get("field_mappings") if isinstance(classification, dict) else []
    if not isinstance(mappings, list) or not mappings:
        return "字段映射：暂无。"
    rows = []
    for mapping in mappings:
        if not isinstance(mapping, dict):
            continue
        standard_label = mapping.get("standard_label") or "待确认"
        standard_field = mapping.get("standard_field") or "-"
        status = {
            "mapped": "已映射",
            "ambiguous": "待确认",
            "unmapped": "未映射",
        }.get(str(mapping.get("status") or ""), str(mapping.get("status") or "-"))
        rows.append(
            [
                mapping.get("source_header") or "-",
                f"{standard_label} / {standard_field}",
                status,
            ]
        )
    return "字段映射：\n\n" + markdown_table(["原始表头", "标准字段", "状态"], rows)


def _excel_change_proposal_table(classification: dict[str, Any]) -> str:
    proposals = classification.get("change_proposals") if isinstance(classification, dict) else []
    if not isinstance(proposals, list) or not proposals:
        return "字段目录建议：暂无待确认变更。"
    rows = []
    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue
        rows.append(
            [
                proposal.get("source_header") or "-",
                proposal.get("suggested_field") or proposal.get("type") or "-",
                proposal.get("standard_label") or "待用户选择",
                "需要弹窗确认",
            ]
        )
    return "字段目录建议：\n\n" + markdown_table(["原始表头", "建议编码", "中文名", "处理要求"], rows)


def format_tool_result(action: str, result: Any) -> str:
    if isinstance(result, dict) and result.get("ok") is not False:
        return format_skill_result(result)
    text = observation_to_text(result)
    if "失败" in text or "错误" in text or "未知工具" in text or "技能已关闭" in text or "error" in text.lower():
        return format_error(text)
    if isinstance(result, (dict, list)):
        return format_skill_result(result)
    if action == "official.query_weather":
        return format_weather_result(text)
    return format_plain_response(text, "执行结果")


def format_agent_reply(action: str, response: str, action_result: Any) -> str:
    if action != "none" and action_result and action_result != "无操作":
        return format_tool_result(action, action_result)
    return format_plain_response(response, "回复")
