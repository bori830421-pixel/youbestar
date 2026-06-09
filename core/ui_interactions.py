from typing import Any


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _confidence_value(value: Any) -> float:
    try:
        return round(float(value or 0), 4)
    except (TypeError, ValueError):
        return 0.0


def _candidate_id(candidate: dict[str, Any]) -> str:
    return _clean_text(
        candidate.get("record_id")
        or candidate.get("id")
        or candidate.get("business_key")
        or candidate.get("title")
    )


def build_chat_interaction(action: str, payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict) or payload.get("ok") is False:
        return None

    kind = _clean_text(payload.get("kind"))
    if kind == "reference_product_match":
        return _reference_product_match_interaction(payload)
    if kind == "excel_preview":
        return _excel_preview_interaction(payload)
    return None


def _reference_product_match_interaction(payload: dict[str, Any]) -> dict[str, Any] | None:
    match = _as_dict(payload.get("match")) or _as_dict(payload.get("data"))
    matches = _as_list(payload.get("matches")) or _as_list(match.get("matches"))
    if not matches:
        return None

    items: list[dict[str, Any]] = []
    for index, item_value in enumerate(matches, start=1):
        item = _as_dict(item_value)
        candidates = []
        for candidate_value in _as_list(item.get("candidates")):
            candidate = _as_dict(candidate_value)
            candidate_id = _candidate_id(candidate)
            if not candidate_id:
                continue
            candidates.append(
                {
                    "id": candidate_id,
                    "record_id": _clean_text(candidate.get("record_id") or candidate.get("id")),
                    "business_key": _clean_text(candidate.get("business_key")),
                    "title": _clean_text(candidate.get("title")),
                    "confidence": _confidence_value(candidate.get("confidence") or candidate.get("score")),
                    "reason": _clean_text(candidate.get("reason")),
                    "fields": _as_dict(candidate.get("fields")),
                }
            )

        best = _as_dict(item.get("best_candidate"))
        best_id = _candidate_id(best)
        source_sku_id = _clean_text(item.get("source_sku_id") or item.get("sku_id"))
        sku = _clean_text(item.get("sku") or item.get("sku_code") or source_sku_id)
        item_id = source_sku_id or sku or f"sku-{index}"
        items.append(
            {
                "id": item_id,
                "source_sku_id": source_sku_id,
                "sku": sku,
                "sku_name": _clean_text(item.get("sku_name")),
                "price": item.get("cost_price") if item.get("cost_price") not in (None, "") else item.get("price", ""),
                "stock": item.get("stock", ""),
                "image_url": _clean_text(item.get("image_url") or item.get("sku_image_url")),
                "status": _clean_text(item.get("status")),
                "selected_candidate_id": best_id,
                "candidates": candidates,
            }
        )

    return {
        "kind": "reference_product_match_review",
        "version": 1,
        "title": "参考商品候选确认",
        "description": "请选择要绑定的资料库 SKU，确认后才会写入图片链接。",
        "endpoint": "/reference-products/confirm-bind",
        "method": "POST",
        "match_id": _clean_text(payload.get("match_id") or match.get("match_id")),
        "capture_id": _clean_text(match.get("capture_id") or payload.get("capture_id")),
        "source_url": _clean_text(match.get("source_url") or payload.get("source_url")),
        "source_title": _clean_text(match.get("title") or payload.get("title")),
        "items": items,
        "actions": [
            {"id": "confirm_selected", "label": "确认选中绑定", "style": "primary"},
            {"id": "skip", "label": "跳过", "style": "secondary"},
        ],
    }


def _excel_preview_interaction(payload: dict[str, Any]) -> dict[str, Any] | None:
    data = _as_dict(payload.get("data"))
    sheets = _as_list(data.get("sheets"))
    if not sheets:
        return None

    standard_fields = _as_list(data.get("standard_fields"))
    table_categories = _as_list(data.get("table_categories"))
    sheet_items = []
    for sheet_value in sheets:
        sheet = _as_dict(sheet_value)
        classification = _as_dict(sheet.get("classification"))
        sheet_items.append(
            {
                "name": _clean_text(sheet.get("name")),
                "header_row": sheet.get("header_row", ""),
                "headers": _as_list(sheet.get("headers")),
                "status": _clean_text(classification.get("status") or "unknown"),
                "category": _clean_text(classification.get("category")),
                "category_label": _clean_text(classification.get("category_label") or "未识别"),
                "confidence": _confidence_value(classification.get("confidence")),
                "needs_confirmation": bool(classification.get("needs_confirmation")),
                "available_categories": _as_list(classification.get("available_categories")) or table_categories,
                "field_mappings": _as_list(classification.get("field_mappings")),
                "change_proposals": _as_list(classification.get("change_proposals")),
            }
        )

    return {
        "kind": "excel_preview_review",
        "version": 1,
        "title": "Excel 表格确认",
        "description": "可在聊天窗口内确认表格分类和字段映射，确认后才会保存修正。",
        "endpoint": "/files/excel/feedback",
        "method": "POST",
        "file_name": _clean_text(data.get("file_name")),
        "saved_path": _clean_text(data.get("saved_path")),
        "classification_summary": _as_dict(data.get("classification_summary")),
        "standard_fields": standard_fields,
        "table_categories": table_categories,
        "sheets": sheet_items,
        "actions": [
            {"id": "confirm_category", "label": "确认分类", "style": "primary"},
            {"id": "confirm_fields", "label": "确认字段", "style": "primary"},
        ],
    }
