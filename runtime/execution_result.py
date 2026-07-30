"""ExecutionResult — result of submitting an order to Broker."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class ExecutionResult:
    success: bool
    contract_id: str
    order_id: str = ""
    status: str = ""          # FILLED | REJECTED | PENDING | ERROR
    filled_price: Optional[float] = None
    filled_volume: Optional[float] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self):
        return f"<ExecutionResult {self.contract_id} {self.status} filled@{self.filled_price}>"
