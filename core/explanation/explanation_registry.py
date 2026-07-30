"""Explanation Registry — store/recall ExplanationReports."""
import logging
from typing import Dict, List, Optional
from core.explanation.explanation_report import ExplanationReport

log = logging.getLogger(__name__)


class ExplanationRegistry:
    def __init__(self):
        self._store: Dict[str, ExplanationReport] = {}

    def register(self, report: ExplanationReport) -> None:
        self._store[report.report_id] = report

    def unregister(self, report_id: str) -> None:
        self._store.pop(report_id, None)

    def get(self, report_id: str) -> Optional[ExplanationReport]:
        return self._store.get(report_id)

    def list(self) -> List[str]:
        return list(self._store.keys())

    def exists(self, report_id: str) -> bool:
        return report_id in self._store
