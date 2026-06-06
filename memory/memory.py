from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


SHORT_TERM_LIMIT = 50
BUSINESS_MEMORY_TYPES = {
    "customer",
    "sku",
    "order",
    "erp_order",
    "finance_report",
    "transaction",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MemoryRecord:
    content: str
    memory_type: str
    module: str = "general"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    confirmed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "memory_type": self.memory_type,
            "module": self.module,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "confirmed": self.confirmed,
        }


class Memory:
    """
    Layered memory skeleton.

    Short-term memory keeps recent conversation context. Long-term memory only
    accepts confirmed business records. Temporary/chatty information is never
    promoted automatically.
    """

    def __init__(self, short_term_limit: int = SHORT_TERM_LIMIT):
        self.short_term_limit = short_term_limit
        self.history: list[dict[str, Any]] = []
        self.temporary: list[dict[str, Any]] = []
        self.long_term: list[MemoryRecord] = []
        self.pending_candidates: list[MemoryRecord] = []

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
            "candidate": record.to_dict(),
        }

    def confirm_pending(self, index: int = -1) -> dict[str, Any]:
        if not self.pending_candidates:
            return {"ok": False, "reason": "no_pending_candidate"}
        try:
            record = self.pending_candidates.pop(index)
        except IndexError:
            return {"ok": False, "reason": "pending_candidate_not_found"}

        record.confirmed = True
        self.long_term.append(record)
        self.compress_long_term()
        return {"ok": True, "record": record.to_dict()}

    def reject_pending(self, index: int = -1) -> dict[str, Any]:
        if not self.pending_candidates:
            return {"ok": False, "reason": "no_pending_candidate"}
        try:
            record = self.pending_candidates.pop(index)
        except IndexError:
            return {"ok": False, "reason": "pending_candidate_not_found"}
        return {"ok": True, "record": record.to_dict()}

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

    def compress_long_term(self) -> None:
        deduped: dict[tuple[str, str, str], MemoryRecord] = {}
        for record in self.long_term:
            key = (record.module, record.memory_type, record.content)
            deduped[key] = record
        self.long_term = list(deduped.values())

    def get_summary(self) -> str:
        recent_history = self.history[-20:]
        return "\n".join(
            f"{item['user']} -> {item['action']} -> {item['result']}" for item in recent_history
        )
