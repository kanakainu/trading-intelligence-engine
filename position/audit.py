"""Position audit trail — record all lifecycle changes."""
from typing import List, Optional
from position.models import PositionAuditEntry


class PositionAuditTrail:
    def __init__(self):
        self._entries: List[PositionAuditEntry] = []

    def record(self, entry: PositionAuditEntry) -> None:
        self._entries.append(entry)

    def get_entries(self, position_id: Optional[str] = None, limit: int = 100) -> List[PositionAuditEntry]:
        results = self._entries
        if position_id:
            results = [e for e in results if e.position_id == position_id]
        return results[-limit:]

    def clear(self) -> None:
        self._entries.clear()
