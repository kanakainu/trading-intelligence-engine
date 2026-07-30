"""Decision — final output of Decision Engine. First layer allowed BUY/SELL/WAIT."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from core.decision.execution_plan import ExecutionPlan


class Action(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"


@dataclass
class Decision:
    decision_id: str
    action: Action
    confidence: float
    reason: str
    setup_id: str
    execution_plan: Optional[ExecutionPlan] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self):
        return f"<Decision {self.decision_id} {self.action} conf={self.confidence:.2f}>"
