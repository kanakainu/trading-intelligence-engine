"""Risk health monitor — aggregates status from Risk Engine components."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from risk.models import RiskHealthReport


class RiskHealthMonitor:
    def __init__(self):
        self._evaluations = 0
        self._rejections = 0
        self._last_evaluation: Optional[datetime] = None
        self._enabled_policies: List[str] = []
        self._status: str = "INITIALIZED"

    def update_evaluation(self, approved: bool, enabled_policies: List[str]) -> None:
        self._evaluations += 1
        if not approved: self._rejections += 1
        self._last_evaluation = datetime.now(timezone.utc)
        self._enabled_policies = enabled_policies
        self._status = "OPERATIONAL"

    def get_report(self) -> RiskHealthReport:
        rejection_rate = self._rejections / self._evaluations if self._evaluations > 0 else 0.0
        return RiskHealthReport(
            status=self._status,
            enabled_policies=self._enabled_policies,
            evaluations=self._evaluations,
            rejection_rate=round(rejection_rate, 2),
            last_evaluation=self._last_evaluation,
        )
