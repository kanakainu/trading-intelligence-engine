"""Decision Registry — store/recall decisions."""
import logging
from typing import Dict, List, Optional
from core.decision.decision import Decision

log = logging.getLogger(__name__)


class DecisionRegistry:
    def __init__(self):
        self._store: Dict[str, Decision] = {}

    def register(self, decision: Decision) -> None:
        self._store[decision.decision_id] = decision

    def unregister(self, decision_id: str) -> None:
        self._store.pop(decision_id, None)

    def get(self, decision_id: str) -> Optional[Decision]:
        return self._store.get(decision_id)

    def list(self) -> List[str]:
        return list(self._store.keys())

    def exists(self, decision_id: str) -> bool:
        return decision_id in self._store
