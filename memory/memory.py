import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SHORT_TERM_LIMIT = 50
DEFAULT_STORAGE_PATH = Path("data") / "memory_long_term.json"
BUSINESS_MEMORY_TYPES = {
    "customer",
    "sku",
    "order",
    "erp_order",
    "finance_report",
    "transaction",
}
BUSINESS_MEMORY_KEYWORDS = {
    "erp_order": ("ERP", "入库", "出库", "采购单", "销售单"),
    "sku": ("SKU", "sku", "货号", "商品编码"),
    "order": ("订单", "下单", "购买", "采购", "销售"),
    "customer": ("客户", "买家", "联系人"),
    "finance_report": ("财务", "报表", "利润", "成本", "应收", "应付"),
    "transaction": ("交易", "付款", "收款", "转账"),
}
NON_MEMORY_ACTIONS = {
    "local.factory_quote",
    "official.query_weather",
    "official.query_market_data",
    "official.web_query",
}
QUOTE_LOOKUP_HINTS = (
    "报价",
    "尺寸",
    "装箱",
    "毛重",
    "净重",
    "成本",
    "利润",
    "含税",
    "含运费",
    "实拍图",
)
ORDER_COMMIT_HINTS = ("下单", "订单", "购买", "采购", "销售", "成交", "付款", "收款")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MemoryRecord:
    content: str
    memory_type: str
    module: str = "general"
    metadata: dict[str, Any] = field(default_factory=dict)
    id: int | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    confirmed: bool = False
    confirmed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "module": self.module,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "confirmed": self.confirmed,
            "confirmed_at": self.confirmed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryRecord":
        return cls(
            id=data.get("id") if isinstance(data.get("id"), int) else None,
            content=str(data.get("content") or ""),
            memory_type=str(data.get("memory_type") or "order"),
            module=str(data.get("module") or "general"),
            metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
            created_at=str(data.get("created_at") or utc_now()),
            updated_at=str(data.get("updated_at") or data.get("created_at") or utc_now()),
            confirmed=bool(data.get("confirmed")),
            confirmed_at=data.get("confirmed_at") if isinstance(data.get("confirmed_at"), str) else None,
        )


class Memory:
    """
    Layered memory skeleton.

    Short-term memory keeps recent conversation context. Long-term memory only
    accepts confirmed business records. Temporary/chatty information is never
    promoted automatically.
    """

    def __init__(
        self,
        short_term_limit: int = SHORT_TERM_LIMIT,
        storage_path: str | Path | None = None,
    ):
        self.short_term_limit = short_term_limit
        self.storage_path = Path(storage_path) if storage_path else None
        self.history: list[dict[str, Any]] = []
        self.temporary: list[dict[str, Any]] = []
        self.long_term: list[MemoryRecord] = []
        self.pending_candidates: list[MemoryRecord] = []
        self.audit_log: list[dict[str, Any]] = []
        self._next_id = 1
        self._load_long_term()

    def add(self, user_input: str, action: str, result: str, module: str = "general") -> None:
        self.history.append(
            {
                "user": user_input,
                "action": action,
                "result": result,
                "module": module,
                "created_at": utc_now(),
            }
        )
        self.history = self.history[-self.short_term_limit :]

    def add_temporary(self, content: str, module: str = "chat", metadata: dict[str, Any] | None = None) -> None:
        self.temporary.append(
            {
                "content": content,
                "module": module,
                "metadata": metadata or {},
                "created_at": utc_now(),
            }
        )

    def clear_temporary(self) -> None:
        self.temporary.clear()

    def _load_long_term(self) -> None:
        if not self.storage_path or not self.storage_path.exists():
            return
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.audit_log.append({"event": "load_failed", "created_at": utc_now()})
            return

        records = payload.get("records") if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            return
        audit_log = payload.get("audit_log") if isinstance(payload, dict) else []
        if isinstance(audit_log, list):
            self.audit_log = [item for item in audit_log if isinstance(item, dict)]
        self.long_term = [
            record
            for record in (MemoryRecord.from_dict(item) for item in records if isinstance(item, dict))
            if record.confirmed and record.content
        ]
        max_id = max((record.id or 0 for record in self.long_term), default=0)
        self._next_id = max_id + 1

    def _save_long_term(self) -> None:
        if not self.storage_path:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": utc_now(),
            "records": [record.to_dict() for record in self.confirmed_long_term()],
            "audit_log": list(self.audit_log[-500:]),
        }
        self.storage_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _audit(self, event: str, record: MemoryRecord | None = None, reason: str = "") -> None:
        self.audit_log.append(
            {
                "event": event,
                "record_id": record.id if record else None,
                "reason": reason,
                "created_at": utc_now(),
            }
        )

    def is_business_memory_type(self, memory_type: str) -> bool:
        return memory_type in BUSINESS_MEMORY_TYPES

    def propose_long_term(
        self,
        content: str,
        memory_type: str,
        module: str = "general",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.is_business_memory_type(memory_type):
            return {
                "ok": False,
                "reason": "not_business_memory",
                "candidate": None,
            }

        record = MemoryRecord(
            content=content.strip(),
            memory_type=memory_type,
            module=module,
            metadata=metadata or {},
            confirmed=False,
        )
        self.pending_candidates.append(record)
        return {
            "ok": True,
            "reason": "confirmation_required",
            "candidate": self._candidate_payload(record),
        }

    def _extract_candidate_metadata(
        self,
        text: str,
        action: str = "none",
        source: str = "auto_detected",
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "source": source,
            "action": action,
        }
        sku_match = re.search(r"\bSKU[-_A-Za-z0-9]*\b", text, re.IGNORECASE)
        if sku_match:
            metadata["sku"] = sku_match.group(0).upper()

        qty_match = re.search(r"(?:共|数量|qty|Qty)?\s*(\d+(?:\.\d+)?)\s*(件|个|箱|套|pcs|PCS)", text)
        if qty_match:
            qty_text = qty_match.group(1)
            metadata["qty"] = int(float(qty_text)) if float(qty_text).is_integer() else float(qty_text)
            metadata["unit"] = qty_match.group(2) or "件"

        customer_match = re.search(r"(客户|买家|联系人)\s*([\u4e00-\u9fa5A-Za-z0-9_-]{1,20})", text)
        if customer_match:
            metadata["entity"] = f"{customer_match.group(1)}{customer_match.group(2)}"
            metadata["customer"] = customer_match.group(2)

        return metadata

    def _candidate_payload(self, record: MemoryRecord) -> dict[str, Any]:
        data = record.to_dict()
        metadata = data["metadata"]
        data.update(
            {
                "entity": metadata.get("entity") or metadata.get("customer") or "",
                "sku": metadata.get("sku") or "",
                "qty": metadata.get("qty"),
                "task_tag": metadata.get("task_tag") or record.module,
                "source": metadata.get("source") or "auto_detected",
            }
        )
        return data

    def detect_business_memory_candidate(
        self,
        user_input: str,
        action: str = "none",
        result: str = "",
        module: str = "general",
    ) -> dict[str, Any]:
        if self._should_skip_candidate_detection(user_input, action, result):
            return {"ok": False, "reason": "query_result_not_memory", "candidate": None}

        text = " ".join([user_input or "", action or "", result or ""])
        for memory_type, keywords in BUSINESS_MEMORY_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                content = (user_input or result or "").strip()
                if not content:
                    return {"ok": False, "reason": "empty_candidate", "candidate": None}
                metadata = self._extract_candidate_metadata(content, action=action)
                metadata["task_tag"] = module
                return self.propose_long_term(
                    content=content,
                    memory_type=memory_type,
                    module=module,
                    metadata=metadata,
                )
        return {"ok": False, "reason": "no_business_signal", "candidate": None}

    def _should_skip_candidate_detection(self, user_input: str, action: str, result: str) -> bool:
        clean_action = (action or "").strip()
        clean_user_input = user_input or ""
        if clean_action in NON_MEMORY_ACTIONS:
            return True

        has_quote_lookup_hint = any(hint in clean_user_input for hint in QUOTE_LOOKUP_HINTS)
        has_order_commit_hint = any(hint in clean_user_input for hint in ORDER_COMMIT_HINTS)
        if has_quote_lookup_hint and not has_order_commit_hint:
            return True

        return False

    def pending_as_dicts(self) -> list[dict[str, Any]]:
        return [self._candidate_payload(record) for record in self.pending_candidates]

    def long_term_as_dicts(self, module: str | None = None) -> list[dict[str, Any]]:
        return [self._candidate_payload(record) for record in self.confirmed_long_term(module)]

    def confirm_pending(self, index: int = -1) -> dict[str, Any]:
        if not self.pending_candidates:
            return {"ok": False, "reason": "no_pending_candidate"}
        try:
            record = self.pending_candidates.pop(index)
        except IndexError:
            return {"ok": False, "reason": "pending_candidate_not_found"}

        now = utc_now()
        record.id = self._next_id
        self._next_id += 1
        record.confirmed = True
        record.confirmed_at = now
        record.updated_at = now
        self.long_term.append(record)
        self.compress_long_term()
        self._save_long_term()
        self._audit("confirm", record)
        return {"ok": True, "record": self._candidate_payload(record)}

    def reject_pending(self, index: int = -1) -> dict[str, Any]:
        if not self.pending_candidates:
            return {"ok": False, "reason": "no_pending_candidate"}
        try:
            record = self.pending_candidates.pop(index)
        except IndexError:
            return {"ok": False, "reason": "pending_candidate_not_found"}
        self._audit("reject", record)
        self._save_long_term()
        return {"ok": True, "record": self._candidate_payload(record)}

    def confirmed_long_term(self, module: str | None = None) -> list[MemoryRecord]:
        records = [record for record in self.long_term if record.confirmed]
        if module:
            records = [record for record in records if record.module == module]
        return records

    def get_model_context(self, module: str | None = None) -> dict[str, Any]:
        return {
            "short_term": list(self.history[-self.short_term_limit :]),
            "long_term": [record.to_dict() for record in self.confirmed_long_term(module)],
        }

    def get_business_summary(self, module: str | None = None, limit: int = 20) -> str:
        lines: list[str] = []
        for record in self.confirmed_long_term(module)[-limit:]:
            metadata = record.metadata
            details = []
            for key in ("entity", "sku", "qty", "unit", "source"):
                if metadata.get(key) not in (None, ""):
                    details.append(f"{key}={metadata[key]}")
            detail_text = f" ({', '.join(details)})" if details else ""
            lines.append(f"- [{record.module}/{record.memory_type}] {record.content}{detail_text}")
        return "\n".join(lines)

    def compress_long_term(self) -> None:
        deduped: dict[tuple[Any, ...], MemoryRecord] = {}
        for record in self.long_term:
            metadata = record.metadata
            entity = metadata.get("entity") or metadata.get("customer")
            sku = metadata.get("sku")
            qty = metadata.get("qty")
            if entity and sku and isinstance(qty, (int, float)):
                key = (record.module, record.memory_type, entity, sku)
                existing = deduped.get(key)
                if existing:
                    existing_qty = existing.metadata.get("qty")
                    if isinstance(existing_qty, (int, float)):
                        existing.metadata["qty"] = existing_qty + qty
                        existing.metadata["quantity"] = existing.metadata["qty"]
                        existing.content = f"{entity} 共买 {sku} {existing.metadata['qty']}{metadata.get('unit') or '件'}"
                        existing.updated_at = utc_now()
                    continue
                metadata["quantity"] = qty
                deduped[key] = record
                continue
            key = (record.module, record.memory_type, record.content)
            deduped[key] = record
        self.long_term = list(deduped.values())

    def get_summary(self) -> str:
        recent_history = self.history[-20:]
        return "\n".join(
            f"{item['user']} -> {item['action']} -> {item['result']}" for item in recent_history
        )
