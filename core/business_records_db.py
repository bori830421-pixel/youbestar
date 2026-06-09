from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.local_runtime import ensure_local_runtime_dirs, local_data_dir, local_runtime_dir


DEFAULT_LIMIT = 20
MAX_LIMIT = 100


BUILTIN_RECORD_SCHEMA: dict[str, dict[str, Any]] = {
    "customer": {
        "label": "客户资料",
        "description": "客户档案、联系人、地址和协作备注。",
        "key_fields": ["customer_id", "customer_code", "name", "customer_name", "phone"],
        "columns": ["record_type", "business_key", "name", "contact", "phone", "updated_at"],
        "fields": {
            "customer_id": "客户ID",
            "customer_code": "客户编码",
            "name": "客户名称",
            "customer_name": "客户名称",
            "contact": "联系人",
            "phone": "联系电话",
        },
    },
    "product": {
        "label": "商品资料",
        "description": "SKU、商品名称、规格、图片和包装等主数据。",
        "key_fields": ["sku", "product_id", "product_code", "name", "product_name"],
        "columns": ["record_type", "business_key", "sku", "name", "category", "updated_at"],
        "fields": {
            "sku": "SKU",
            "product_id": "产品ID",
            "product_code": "产品编码",
            "name": "产品名称",
            "product_name": "产品名称",
            "category": "品类",
            "spec": "规格",
        },
    },
    "order": {
        "label": "订单资料",
        "description": "销售订单、客户订单和订单进度。",
        "key_fields": ["order_no", "order_id", "customer_name"],
        "columns": ["record_type", "business_key", "order_no", "customer_name", "amount", "status", "updated_at"],
        "fields": {
            "order_no": "订单号",
            "order_id": "订单ID",
            "customer_name": "客户名称",
            "amount": "金额",
            "status": "状态",
        },
    },
    "quote": {
        "label": "报价资料",
        "description": "通用报价资料；工厂报价库仍由 local.factory_quote 管理。",
        "key_fields": ["quote_no", "quote_id", "sku", "customer_name"],
        "columns": ["record_type", "business_key", "quote_no", "customer_name", "sku", "price", "updated_at"],
        "fields": {
            "quote_no": "报价单号",
            "quote_id": "报价ID",
            "customer_name": "客户名称",
            "sku": "SKU",
            "price": "报价",
        },
    },
    "inventory": {
        "label": "库存资料",
        "description": "仓库、库存数量、批次和可用库存。",
        "key_fields": ["sku", "warehouse", "inventory_id"],
        "columns": ["record_type", "business_key", "sku", "warehouse", "quantity", "updated_at"],
        "fields": {
            "inventory_id": "库存ID",
            "sku": "SKU",
            "warehouse": "仓库",
            "quantity": "数量",
            "unit": "单位",
        },
    },
    "purchase": {
        "label": "采购资料",
        "description": "采购单、供应商采购和采购进度。",
        "key_fields": ["purchase_no", "purchase_id", "supplier_name"],
        "columns": ["record_type", "business_key", "purchase_no", "supplier_name", "amount", "status", "updated_at"],
        "fields": {
            "purchase_no": "采购单号",
            "purchase_id": "采购ID",
            "supplier_name": "供应商",
            "amount": "金额",
            "status": "状态",
        },
    },
    "finance": {
        "label": "财务资料",
        "description": "收支、应收应付、费用和账户资料。",
        "key_fields": ["voucher_no", "invoice_no", "finance_id"],
        "columns": ["record_type", "business_key", "voucher_no", "invoice_no", "amount", "updated_at"],
        "fields": {
            "finance_id": "财务ID",
            "voucher_no": "凭证号",
            "invoice_no": "发票号",
            "amount": "金额",
            "account": "科目",
        },
    },
    "logistics": {
        "label": "物流资料",
        "description": "物流单号、承运商、发货和签收状态。",
        "key_fields": ["tracking_no", "shipment_no", "logistics_id", "order_no"],
        "columns": ["record_type", "business_key", "tracking_no", "carrier", "status", "updated_at"],
        "fields": {
            "logistics_id": "物流ID",
            "tracking_no": "运单号",
            "shipment_no": "出货单号",
            "order_no": "订单号",
            "carrier": "承运商",
            "status": "状态",
        },
    },
    "excel_table": {
        "label": "Excel 表格归档",
        "description": "已确认字段映射后的通用 Excel 表格归档记录。",
        "key_fields": ["table_id", "source_path", "file_name", "sheet_name", "title"],
        "columns": ["record_type", "business_key", "file_name", "sheet_name", "category_label", "row_count", "updated_at"],
        "fields": {
            "table_id": "表格ID",
            "file_name": "文件名",
            "source_path": "文件路径",
            "sheet_name": "工作表",
            "category": "分类编码",
            "category_label": "分类",
            "row_count": "行数",
            "column_count": "列数",
            "mapping_status": "映射状态",
            "field_mappings": "字段映射",
            "headers": "表头",
            "rows": "数据行",
            "confirmed_by": "确认人",
        },
    },
    "general": {
        "label": "通用资料",
        "description": "未归入专门业务类型的共享办公资料。",
        "key_fields": ["title", "name", "code"],
        "columns": ["record_type", "business_key", "title", "updated_at"],
        "fields": {"title": "标题", "name": "名称", "content": "内容", "code": "编码"},
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def business_records_db_path() -> Path:
    return local_data_dir() / "business_records.sqlite3"


def business_records_audit_log_path() -> Path:
    return local_runtime_dir() / "logs" / "business_records_changes.jsonl"


def business_records_schema_path() -> Path:
    return local_runtime_dir() / "config" / "business_records_schema.json"


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_record_type(value: Any) -> str:
    text = clean_text(value).lower().replace("-", "_")
    text = re.sub(r"[^a-z0-9_]+", "_", text).strip("_")
    return text or "general"


def normalize_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[,，、;；\s]+", value)
    elif isinstance(value, list):
        parts = [str(item) for item in value]
    else:
        parts = [str(value)]
    tags: list[str] = []
    for part in parts:
        tag = clean_text(part)
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _schema_copy() -> dict[str, dict[str, Any]]:
    schema: dict[str, dict[str, Any]] = {}
    for record_type, config in BUILTIN_RECORD_SCHEMA.items():
        schema[record_type] = {
            "label": config.get("label") or record_type,
            "description": config.get("description") or "共享办公资料。",
            "key_fields": list(config.get("key_fields") or []),
            "columns": list(config.get("columns") or []),
            "fields": dict(config.get("fields") or {}),
        }
    return schema


def _write_default_schema_file(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "2026-06-09.business-records-v1",
        "record_types": {
            record_type: {
                "label": config["label"],
                "description": config["description"],
                "key_fields": config["key_fields"],
                "columns": config["columns"],
                "fields": config["fields"],
            }
            for record_type, config in _schema_copy().items()
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_business_record_schema(schema_path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    schema = _schema_copy()
    path = Path(schema_path) if schema_path else business_records_schema_path()
    _write_default_schema_file(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError):
        return schema

    raw_types = raw.get("record_types") if isinstance(raw, dict) else None
    if isinstance(raw_types, dict):
        iterable = raw_types.items()
    elif isinstance(raw_types, list):
        iterable = ((item.get("code") or item.get("record_type"), item) for item in raw_types if isinstance(item, dict))
    else:
        iterable = []

    for raw_type, raw_config in iterable:
        record_type = normalize_record_type(raw_type)
        if not record_type or not isinstance(raw_config, dict):
            continue
        config = dict(schema.get(record_type, {}))
        config.setdefault("label", record_type)
        config.setdefault("description", "共享办公资料。")
        config.setdefault("key_fields", ["id", "code", "name"])
        config.setdefault("columns", ["record_type", "business_key", "title", "updated_at"])
        config.setdefault("fields", {})
        if isinstance(raw_config.get("label"), str):
            config["label"] = raw_config["label"]
        if isinstance(raw_config.get("description"), str):
            config["description"] = raw_config["description"]
        if isinstance(raw_config.get("key_fields"), list):
            config["key_fields"] = [clean_text(item) for item in raw_config["key_fields"] if clean_text(item)]
        if isinstance(raw_config.get("columns"), list):
            config["columns"] = [clean_text(item) for item in raw_config["columns"] if clean_text(item)]
        if isinstance(raw_config.get("fields"), dict):
            fields = dict(config.get("fields") or {})
            fields.update({clean_text(key): value for key, value in raw_config["fields"].items() if clean_text(key)})
            config["fields"] = fields
        schema[record_type] = config
    return schema


def normalize_business_record_type(value: Any, schema: dict[str, dict[str, Any]]) -> str:
    record_type = normalize_record_type(value)
    if record_type not in schema:
        raise ValueError(f"unsupported record_type: {record_type or '-'}")
    return record_type


def make_record_id(record_type: str) -> str:
    return f"{normalize_record_type(record_type)}-{uuid.uuid4().hex[:12]}"


class BusinessRecordsDB:
    def __init__(
        self,
        db_path: str | Path | None = None,
        audit_log_path: str | Path | None = None,
        schema_path: str | Path | None = None,
    ) -> None:
        self.db_path = Path(db_path) if db_path else business_records_db_path()
        self.audit_log_path = Path(audit_log_path) if audit_log_path else business_records_audit_log_path()
        self.schema_path = Path(schema_path) if schema_path else business_records_schema_path()
        self.schema = load_business_record_schema(self.schema_path)

    def ensure_ready(self) -> None:
        ensure_local_runtime_dirs()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.schema_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS business_records (
                    id TEXT PRIMARY KEY,
                    record_type TEXT NOT NULL,
                    business_key TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    data_json TEXT NOT NULL DEFAULT '{}',
                    fields_json TEXT NOT NULL DEFAULT '{}',
                    search_text TEXT NOT NULL DEFAULT '',
                    created_by TEXT NOT NULL DEFAULT '',
                    updated_by TEXT NOT NULL DEFAULT '',
                    source_ip TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            existing_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(business_records)").fetchall()
            }
            column_defaults = {
                "business_key": "TEXT NOT NULL DEFAULT ''",
                "title": "TEXT NOT NULL DEFAULT ''",
                "content": "TEXT NOT NULL DEFAULT ''",
                "tags_json": "TEXT NOT NULL DEFAULT '[]'",
                "status": "TEXT NOT NULL DEFAULT ''",
                "source": "TEXT NOT NULL DEFAULT ''",
                "data_json": "TEXT NOT NULL DEFAULT '{}'",
                "fields_json": "TEXT NOT NULL DEFAULT '{}'",
                "search_text": "TEXT NOT NULL DEFAULT ''",
                "created_by": "TEXT NOT NULL DEFAULT ''",
                "updated_by": "TEXT NOT NULL DEFAULT ''",
                "source_ip": "TEXT NOT NULL DEFAULT ''",
                "created_at": "TEXT NOT NULL DEFAULT ''",
                "updated_at": "TEXT NOT NULL DEFAULT ''",
            }
            for column, definition in column_defaults.items():
                if column not in existing_columns:
                    connection.execute(f"ALTER TABLE business_records ADD COLUMN {column} {definition}")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_business_records_type ON business_records(record_type)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_business_records_updated ON business_records(updated_at)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_business_records_search_text ON business_records(search_text)")
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_business_records_type_business_key
                ON business_records(record_type, business_key)
                WHERE business_key <> ''
                """
            )
            connection.commit()

    def list_types(self) -> list[dict[str, Any]]:
        self.ensure_ready()
        counts = self.type_counts()
        return [
            {
                "record_type": record_type,
                "type": record_type,
                "value": record_type,
                "code": record_type,
                "label": clean_text(config.get("label")) or record_type,
                "description": clean_text(config.get("description")) or "共享办公资料。",
                "key_fields": list(config.get("key_fields") or []),
                "fields": dict(config.get("fields") or {}),
                "columns": list(config.get("columns") or []),
                "count": counts.get(record_type, 0),
            }
            for record_type, config in sorted(self.schema.items())
        ]

    def type_counts(self) -> dict[str, int]:
        self.ensure_ready()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT record_type, COUNT(*) AS count
                FROM business_records
                GROUP BY record_type
                """
            ).fetchall()
        return {str(row["record_type"]): int(row["count"]) for row in rows}

    def upsert_record(
        self,
        record_type: str,
        fields: dict[str, Any],
        business_key: str | None = None,
        title: str | None = None,
        content: str | None = None,
        tags: list[Any] | str | None = None,
        status: str | None = None,
        actor: str | None = None,
        source_ip: str | None = None,
        source: str | None = None,
        record_id: str | None = None,
    ) -> dict[str, Any]:
        self.ensure_ready()
        clean_type = normalize_business_record_type(record_type, self.schema)
        clean_fields = dict(fields or {})
        if content is not None and "content" not in clean_fields:
            clean_fields["content"] = content
        clean_key = self._business_key(clean_type, clean_fields, business_key)
        generated_key = not clean_text(business_key) and clean_key.startswith("generated:")
        clean_title = clean_text(
            title
            if title is not None
            else clean_fields.get("name")
            or clean_fields.get("title")
            or clean_fields.get("product_name")
            or clean_fields.get("customer_name")
            or clean_key
        )
        clean_tags = normalize_tags(tags if tags is not None else clean_fields.get("tags"))
        clean_status = clean_text(status if status is not None else clean_fields.get("status"))
        clean_actor = clean_text(actor or "operator")
        clean_source_ip = clean_text(source_ip)
        clean_source = clean_text(source)
        now = utc_now()
        explicit_record_id = clean_text(record_id)

        with self._connect() as connection:
            existing = None
            if explicit_record_id:
                existing = connection.execute("SELECT * FROM business_records WHERE id = ?", (explicit_record_id,)).fetchone()
            if existing is None:
                existing = connection.execute(
                    "SELECT * FROM business_records WHERE record_type = ? AND business_key = ?",
                    (clean_type, clean_key),
                ).fetchone()

            if existing:
                before = self._row_to_record(existing)
                old_fields = dict(before.get("fields") or {})
                merged_fields = dict(old_fields)
                merged_fields.update(clean_fields)
                final_title = clean_title if title is not None else before.get("title") or clean_title
                final_tags = clean_tags if tags is not None or "tags" in clean_fields else list(before.get("tags") or [])
                final_status = clean_status if status is not None or "status" in clean_fields else clean_text(before.get("status"))
                final_content = clean_text(content) if content is not None else clean_text(merged_fields.get("content"))
                saved_id = str(existing["id"])
                action = "update"
                connection.execute(
                    """
                    UPDATE business_records
                    SET title = ?, content = ?, tags_json = ?, status = ?, source = ?,
                        data_json = ?, fields_json = ?, search_text = ?,
                        updated_by = ?, source_ip = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        final_title,
                        final_content,
                        _json_dumps(final_tags),
                        final_status,
                        clean_source or before.get("source", ""),
                        _json_dumps(merged_fields),
                        _json_dumps(merged_fields),
                        self._search_text(clean_type, clean_key, final_title, final_content, merged_fields, final_tags, final_status),
                        clean_actor,
                        clean_source_ip,
                        now,
                        saved_id,
                    ),
                )
            else:
                before = None
                merged_fields = clean_fields
                final_title = clean_title
                final_tags = clean_tags
                final_status = clean_status
                final_content = clean_text(content) if content is not None else clean_text(merged_fields.get("content"))
                saved_id = explicit_record_id or make_record_id(clean_type)
                action = "insert"
                connection.execute(
                    """
                    INSERT INTO business_records (
                        id, record_type, business_key, title, content, tags_json, status, source,
                        data_json, fields_json, search_text, created_by, updated_by, source_ip,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        saved_id,
                        clean_type,
                        clean_key,
                        final_title,
                        final_content,
                        _json_dumps(final_tags),
                        final_status,
                        clean_source,
                        _json_dumps(merged_fields),
                        _json_dumps(merged_fields),
                        self._search_text(clean_type, clean_key, final_title, final_content, merged_fields, final_tags, final_status),
                        clean_actor,
                        clean_actor,
                        clean_source_ip,
                        now,
                        now,
                    ),
                )

            connection.commit()
            saved = connection.execute("SELECT * FROM business_records WHERE id = ?", (saved_id,)).fetchone()
            after = self._row_to_record(saved)

        changed_fields = self._changed_fields(before.get("fields", {}) if before else {}, after.get("fields", {}))
        self._append_audit_log(
            {
                "timestamp": now,
                "operation": "upsert",
                "action": action,
                "record_id": after["id"],
                "record_type": clean_type,
                "business_key": clean_key,
                "actor": clean_actor,
                "source_ip": clean_source_ip,
                "source": clean_source,
                "changed_fields": changed_fields,
                "before": before,
                "after": after,
            }
        )
        after["generated_key"] = generated_key
        after["action"] = action
        after["changed_fields"] = changed_fields
        return after

    def query_records(
        self,
        record_type: str | None = None,
        business_key: str | None = None,
        query: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict[str, Any]]:
        self.ensure_ready()
        clean_type = normalize_business_record_type(record_type, self.schema) if clean_text(record_type) else None
        clean_key = clean_text(business_key)
        clean_query = clean_text(query).lower()
        clean_limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
        clauses: list[str] = []
        values: list[Any] = []
        if clean_type:
            clauses.append("record_type = ?")
            values.append(clean_type)
        if clean_key:
            clauses.append("business_key = ?")
            values.append(clean_key)
        if clean_query:
            clauses.append(
                "(LOWER(search_text) LIKE ? OR LOWER(business_key) LIKE ? OR LOWER(title) LIKE ? OR LOWER(content) LIKE ? OR LOWER(data_json) LIKE ? OR LOWER(fields_json) LIKE ?)"
            )
            like = f"%{clean_query}%"
            values.extend([like, like, like, like, like, like])
        where_sql = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM business_records
                {where_sql}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (*values, clean_limit),
            ).fetchall()
        records = [self._row_to_record(row) for row in rows]
        clean_filters = {clean_text(key): value for key, value in (filters or {}).items() if value not in (None, "")}
        if clean_filters:
            records = [record for record in records if self._matches_filters(record, clean_filters)]
        return records[:clean_limit]

    def status(self) -> dict[str, Any]:
        self.ensure_ready()
        with self._connect() as connection:
            total = connection.execute("SELECT COUNT(*) FROM business_records").fetchone()[0]
            latest = connection.execute("SELECT MAX(updated_at) FROM business_records").fetchone()[0]
        return {
            "database_path": str(self.db_path),
            "schema_path": str(self.schema_path),
            "change_log_path": str(self.audit_log_path),
            "record_count": int(total),
            "latest_updated_at": latest or "",
            "record_types": self.list_types(),
            "type_counts": [
                {"record_type": record_type, "count": count}
                for record_type, count in sorted(self.type_counts().items())
            ],
        }

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def _row_to_record(self, row: sqlite3.Row) -> dict[str, Any]:
        fields = _json_loads(row["fields_json"], {})
        if not isinstance(fields, dict) or not fields:
            fields = _json_loads(row["data_json"], {})
        tags = _json_loads(row["tags_json"], [])
        return {
            "id": row["id"],
            "record_id": row["id"],
            "record_type": row["record_type"],
            "type": row["record_type"],
            "record_type_label": self.schema.get(row["record_type"], {}).get("label", row["record_type"]),
            "business_key": row["business_key"],
            "title": row["title"],
            "content": row["content"],
            "summary": row["content"] or self._summary_from_fields(fields),
            "fields": fields if isinstance(fields, dict) else {},
            "data": fields if isinstance(fields, dict) else {},
            "tags": tags if isinstance(tags, list) else [],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "created_by": row["created_by"],
            "updated_by": row["updated_by"],
            "source_ip": row["source_ip"],
            "source": row["source"],
        }

    def _business_key(self, record_type: str, fields: dict[str, Any], explicit_key: str | None) -> str:
        if clean_text(explicit_key):
            return clean_text(explicit_key)
        for field in self.schema.get(record_type, {}).get("key_fields") or []:
            value = fields.get(field)
            if clean_text(value):
                return clean_text(value)
        for fallback in ("business_key", "key", "id", "code", "sku", "name", "title"):
            value = fields.get(fallback)
            if clean_text(value):
                return clean_text(value)
        return f"generated:{uuid.uuid4().hex}"

    def _search_text(
        self,
        record_type: str,
        business_key: str,
        title: str,
        content: str,
        fields: dict[str, Any],
        tags: list[Any],
        status_value: str,
    ) -> str:
        parts = [record_type, business_key, title, content, status_value, *[str(tag) for tag in tags]]
        for key, value in fields.items():
            parts.append(str(key))
            parts.append(str(value))
        return " ".join(part for part in parts if part).lower()

    def _matches_filters(self, record: dict[str, Any], filters: dict[str, Any]) -> bool:
        fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
        for key, expected in filters.items():
            actual = record.get(key, fields.get(key))
            if str(actual) != str(expected):
                return False
        return True

    def _changed_fields(self, before: dict[str, Any], after: dict[str, Any]) -> list[str]:
        return sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))

    def _summary_from_fields(self, fields: dict[str, Any]) -> str:
        pairs = []
        for key, value in fields.items():
            if value in (None, ""):
                continue
            pairs.append(f"{key}: {value}")
            if len(pairs) >= 4:
                break
        return "；".join(pairs)

    def _append_audit_log(self, entry: dict[str, Any]) -> None:
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_log_path.open("a", encoding="utf-8") as handle:
            handle.write(_json_dumps(entry) + "\n")


def default_db() -> BusinessRecordsDB:
    return BusinessRecordsDB()
