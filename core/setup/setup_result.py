"""SetupResult — output of Setup Engine evaluation."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List


class SetupStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass
class SetupResult:
    setup_id: str
    status: SetupStatus
    score: float = 0.0
    confidence: float = 0.0
    matched_rules: List[str] = field(default_factory=list)
    failed_rules: List[str] = field(default_factory=list)
    missing_facts: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self):
        return f"<SetupResult {self.setup_id} {self.status} score={self.score:.2f}>"
