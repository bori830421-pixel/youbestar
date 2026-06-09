from __future__ import annotations

from typing import Any

from core.business_records_db import BusinessRecordsDB, clean_text, default_db, normalize_record_type


def _db(params: dict[str, Any]) -> BusinessRecordsDB:
    return BusinessRecordsDB(
        db_path=params.get("database_path"),
        audit_log_path=params.get("audit_log_path"),
        schema_path=params.get("schema_path"),
    )


def _actor(params: dict[str, Any]) -> str:
    return clean_text(params.get("actor") or params.get("updated_by") or params.get("created_by") or "operator")


def _source_ip(params: dict[str, Any]) -> str:
    return clean_text(params.get("source_ip") or params.get("client_ip") or "")


def _fields_from_params(params: dict[str, Any]) -> dict[str, Any]:
    fields = params.get("fields")
    if isinstance(fields, dict):
        return dict(fields)
    data = params.get("data")
    if isinstance(data, dict):
        return dict(data)
    result: dict[str, Any] = {}
    for key in (
        "title",
        "name",
        "content",
        "summary",
        "text",
        "customer_name",
        "sku",
        "product_name",
        "order_no",
        "quote_no",
        "purchase_no",
        "tracking_no",
        "warehouse",
        "amount",
        "price",
        "quantity",
        "status",
        "table_id",
        "file_name",
        "source_path",
        "sheet_name",
        "category",
        "category_label",
        "row_count",
        "column_count",
        "mapping_status",
        "field_mappings",
        "headers",
        "rows",
        "confirmed_by",
    ):
        if params.get(key) not in (None, ""):
            result[key] = params.get(key)
    return result


def _field_label(database: BusinessRecordsDB, record_type: str, field: str) -> str:
    if field == "record_type":
        return "类型"
    if field == "business_key":
        return "业务键"
    if field == "updated_at":
        return "更新时间"
    if field == "title":
        return "标题"
    config = database.schema.get(record_type, {})
    labels = config.get("fields") if isinstance(config.get("fields"), dict) else {}
    return str(labels.get(field) or field)


def _record_value(record: dict[str, Any], field: str) -> Any:
    if field == "record_type":
        return record.get("record_type_label") or record.get("record_type") or "-"
    if field == "business_key":
        return record.get("business_key") or "-"
    if field == "updated_at":
        return record.get("updated_at") or "-"
    if field == "title":
        return record.get("title") or "-"
    if field == "status":
        return record.get("status") or record.get("fields", {}).get("status") or "-"
    fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
    return fields.get(field, "-")


def _columns_for_records(database: BusinessRecordsDB, record_type: str | None, records: list[dict[str, Any]]) -> list[str]:
    clean_type = normalize_record_type(record_type or records[0]["record_type"] if records else record_type or "general")
    config = database.schema.get(clean_type, {})
    columns = list(config.get("columns") or ["record_type", "business_key", "title", "updated_at"])
    return [_field_label(database, clean_type, column) for column in columns]


def _rows_for_records(database: BusinessRecordsDB, record_type: str | None, records: list[dict[str, Any]]) -> list[list[Any]]:
    if not records:
        return []
    clean_type = normalize_record_type(record_type or records[0]["record_type"])
    config = database.schema.get(clean_type, {})
    columns = list(config.get("columns") or ["record_type", "business_key", "title", "updated_at"])
    return [[_record_value(record, column) for column in columns] for record in records]


def list_record_types(params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    database = _db(params)
    status = database.status()
    types = status["record_types"]
    rows = [
        [
            item["label"],
            item["record_type"],
            item["count"],
            item["description"],
        ]
        for item in types
    ]
    return {
        "ok": True,
        "kind": "business_record_types",
        "title": "共享办公资料类型",
        "columns": ["类型", "编码", "记录数", "说明"],
        "rows": rows,
        "summary": {
            "资料库": status["database_path"],
            "记录数": status["record_count"],
            "类型数": len(types),
        },
        "types": types,
        "record_types": types,
        "data": status,
    }


def query_business_records(params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    database = _db(params)
    record_type = clean_text(params.get("record_type") or params.get("type"))
    business_key = clean_text(params.get("business_key") or params.get("key"))
    limit = int(params.get("limit") or 20)
    filters = params.get("filters") if isinstance(params.get("filters"), dict) else {}
    records = database.query_records(
        record_type=record_type or None,
        business_key=business_key or None,
        query=clean_text(params.get("query") or params.get("keyword") or params.get("q")),
        filters=filters,
        limit=limit,
    )
    columns = _columns_for_records(database, record_type or None, records)
    rows = _rows_for_records(database, record_type or None, records)
    return {
        "ok": True,
        "kind": "business_records_query",
        "title": "共享办公资料查询结果",
        "columns": columns,
        "rows": rows,
        "summary": {
            "关键词": clean_text(params.get("query") or params.get("keyword") or params.get("q")) or "-",
            "类型": database.schema.get(normalize_record_type(record_type), {}).get("label", "全部类型") if record_type else "全部类型",
            "匹配数量": len(records),
        },
        "records": records,
        "data": {"records": records, "record_type": record_type, "business_key": business_key},
    }


def upsert_business_record(params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    database = _db(params)
    fields = _fields_from_params(params)
    content = clean_text(params.get("content") or params.get("summary") or params.get("text"))
    if content and "content" not in fields:
        fields["content"] = content
    try:
        record = database.upsert_record(
            record_type=clean_text(params.get("record_type") or params.get("type") or "general"),
            fields=fields,
            business_key=clean_text(params.get("business_key") or params.get("key")),
            title=clean_text(params.get("title") or params.get("name")) or None,
            content=content or None,
            tags=params.get("tags"),
            status=clean_text(params.get("status")) or None,
            actor=_actor(params),
            source_ip=_source_ip(params),
            source=clean_text(params.get("source")) or None,
            record_id=clean_text(params.get("id") or params.get("record_id")) or None,
        )
    except ValueError as exc:
        return {
            "ok": False,
            "kind": "business_records_error",
            "title": "共享办公资料写入失败",
            "error": str(exc),
        }

    columns = _columns_for_records(database, record["record_type"], [record])
    rows = _rows_for_records(database, record["record_type"], [record])
    action_label = "更新" if record.get("action") == "update" else "新增"
    return {
        "ok": True,
        "kind": "business_record_upsert",
        "title": "共享办公资料已保存",
        "columns": columns,
        "rows": rows,
        "summary": {
            "动作": action_label,
            "业务键": record["business_key"],
            "类型": record["record_type_label"],
            "经办人": record.get("updated_by") or "-",
            "来源IP": record.get("source_ip") or "-",
        },
        "message": f"记录已{action_label}。",
        "record": record,
        "records": [record],
        "data": {"record": record},
    }


def status_business_records(params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    database = _db(params)
    status = database.status()
    rows = [
        [item["label"], item["record_type"], item["count"]]
        for item in status.get("record_types", [])
    ]
    return {
        "ok": True,
        "kind": "business_records_status",
        "title": "共享办公资料库状态",
        "columns": ["类型", "编码", "记录数"],
        "rows": rows,
        "summary": {
            "资料库": status["database_path"],
            "记录数": status["record_count"],
            "最近更新": status["latest_updated_at"] or "-",
        },
        "data": status,
    }


def run(params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    operation = clean_text(params.get("operation") or params.get("action") or "query").lower()
    if operation in {"list_types", "types", "record_types", "schema"}:
        return list_record_types(params)
    if operation in {"upsert", "save", "insert", "update", "create", "write"}:
        return upsert_business_record(params)
    if operation in {"status", "info"}:
        return status_business_records(params)
    return query_business_records(params)
