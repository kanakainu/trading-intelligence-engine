"""ExecutionPlan — blueprint for execution, no broker/API calls."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class ExecutionPlan:
    entry_type: str = ""        # "market" | "limit" | "stop"
    entry_zone: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    risk_profile: str = ""      # "low" | "medium" | "high"
    expiration: Optional[datetime] = None
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_complete(self) -> bool:
        return bool(self.entry_type and self.stop_loss and self.take_profit)
