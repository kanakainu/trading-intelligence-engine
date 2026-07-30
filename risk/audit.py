"""Risk audit trail — records every risk evaluation for transparency and debug."""
from typing import List
from risk.models import RiskAuditRecord


class RiskAuditTrail:
    def __init__(self):
        self._records: List[RiskAuditRecord] = []

    def record(self, audit_record: RiskAuditRecord) -> None:
        self._records.append(audit_record)

    def get_records(self, limit: int = 100) -> List[RiskAuditRecord]:
        return self._records[-limit:]

    def clear(self) -> None:
        self._records.clear()
