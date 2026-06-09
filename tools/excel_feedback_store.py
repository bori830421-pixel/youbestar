from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.local_runtime import local_data_dir


DEFAULT_SCOPE = "template"
VALID_SCOPES = {"template", "global"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_header_key(value: Any) -> str:
    text = _clean_text(value).lower()
    for left, right in (("（", "("), ("）", ")")):
        text = text.replace(left, right)
    for char in " \t\r\n:：,，;；()（）[]【】/\\_-":
        text = text.replace(char, "")
    return text


def header_signature(headers: list[str]) -> str:
    normalized = [normalize_header_key(header) for header in headers]
    raw = "|".join(normalized)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def feedback_db_path() -> Path:
    return local_data_dir() / "excel_feedback.sqlite3"


@contextmanager
def _connect(path: Path | None = None):
    db_path = path or feedback_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        _ensure_schema(connection)
        yield connection
    finally:
        connection.close()


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS excel_category_feedback (
            id TEXT PRIMARY KEY,
            header_signature TEXT NOT NULL,
            scope TEXT NOT NULL,
            sheet_name TEXT,
            category TEXT NOT NULL,
            previous_category TEXT,
            headers_json TEXT NOT NULL,
            actor TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS excel_field_mapping_feedback (
            id TEXT PRIMARY KEY,
            header_signature TEXT NOT NULL,
            header_key TEXT NOT NULL,
            scope TEXT NOT NULL,
            source_header TEXT NOT NULL,
            standard_field TEXT NOT NULL,
            previous_field TEXT,
            headers_json TEXT NOT NULL,
            actor TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_excel_category_feedback_template ON excel_category_feedback(header_signature, created_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_excel_field_feedback_template ON excel_field_mapping_feedback(header_signature, header_key, created_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_excel_field_feedback_global ON excel_field_mapping_feedback(scope, header_key, created_at)")
    connection.commit()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean_text(part) for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def save_excel_feedback(payload: dict[str, Any]) -> dict[str, Any]:
    headers = [_clean_text(header) for header in payload.get("headers") or []]
    if not headers:
        return {"ok": False, "message": "缺少表头，无法保存 Excel 修正反馈。"}

    scope = _clean_text(payload.get("scope") or DEFAULT_SCOPE).lower()
    if scope not in VALID_SCOPES:
        return {"ok": False, "message": "scope 只能是 template 或 global。"}

    signature = header_signature(headers)
    headers_json = json.dumps(headers, ensure_ascii=False)
    actor = _clean_text(payload.get("actor") or "operator")
    sheet_name = _clean_text(payload.get("sheet_name") or payload.get("sheetName"))
    now = _utc_now()
    saved: list[dict[str, Any]] = []

    with _connect() as connection:
        category = _clean_text(payload.get("category"))
        if category:
            feedback_id = _stable_id("xcf", signature, category, scope, now)
            connection.execute(
                """
                INSERT INTO excel_category_feedback (
                    id, header_signature, scope, sheet_name, category,
                    previous_category, headers_json, actor, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback_id,
                    signature,
                    scope,
                    sheet_name,
                    category,
                    _clean_text(payload.get("previous_category") or payload.get("previousCategory")),
                    headers_json,
                    actor,
                    now,
                ),
            )
            saved.append({"type": "category", "id": feedback_id, "category": category, "scope": scope})

        field_mappings = payload.get("field_mappings") or payload.get("fieldMappings") or {}
        if isinstance(field_mappings, dict):
            for source_header, standard_field in field_mappings.items():
                clean_header = _clean_text(source_header)
                clean_field = _clean_text(standard_field)
                if not clean_header or not clean_field:
                    continue
                header_key = normalize_header_key(clean_header)
                feedback_id = _stable_id("xff", signature, header_key, clean_field, scope, now)
                connection.execute(
                    """
                    INSERT INTO excel_field_mapping_feedback (
                        id, header_signature, header_key, scope, source_header,
                        standard_field, previous_field, headers_json, actor, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        feedback_id,
                        signature,
                        header_key,
                        scope,
                        clean_header,
                        clean_field,
                        _clean_text(payload.get("previous_field") or payload.get("previousField")),
                        headers_json,
                        actor,
                        now,
                    ),
                )
                saved.append(
                    {
                        "type": "field_mapping",
                        "id": feedback_id,
                        "source_header": clean_header,
                        "standard_field": clean_field,
                        "scope": scope,
                    }
                )
        connection.commit()

    return {
        "ok": True,
        "saved": saved,
        "header_signature": signature,
        "database": str(feedback_db_path()),
    }


def load_excel_feedback(headers: list[str]) -> dict[str, Any]:
    clean_headers = [_clean_text(header) for header in headers]
    if not clean_headers:
        return {"category": "", "field_mappings": {}, "header_signature": ""}
    signature = header_signature(clean_headers)
    header_keys = [normalize_header_key(header) for header in clean_headers]
    field_mappings: dict[str, dict[str, Any]] = {}

    try:
        with _connect() as connection:
            category_row = connection.execute(
                """
                SELECT * FROM excel_category_feedback
                WHERE header_signature = ? AND scope = 'template'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (signature,),
            ).fetchone()

            for header_key in header_keys:
                template_row = connection.execute(
                    """
                    SELECT * FROM excel_field_mapping_feedback
                    WHERE header_signature = ? AND header_key = ? AND scope = 'template'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (signature, header_key),
                ).fetchone()
                global_row = connection.execute(
                    """
                    SELECT * FROM excel_field_mapping_feedback
                    WHERE header_key = ? AND scope = 'global'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (header_key,),
                ).fetchone()
                row = template_row or global_row
                if row:
                    field_mappings[header_key] = dict(row)
    except sqlite3.Error:
        return {"category": "", "field_mappings": {}, "header_signature": signature}

    return {
        "category": category_row["category"] if category_row else "",
        "category_feedback": dict(category_row) if category_row else None,
        "field_mappings": field_mappings,
        "header_signature": signature,
    }
