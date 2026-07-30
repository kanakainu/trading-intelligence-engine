"""ExecutionContract — standard payload for any broker adapter. No order sent here."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

BUY  = "BUY"
SELL = "SELL"
WAIT = "WAIT"
SKIP = "SKIP"


@dataclass
class ExecutionContract:
    contract_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    action: str = ""                   # BUY | SELL | WAIT | SKIP
    symbol: str = ""                   # XAUUSD
    methodology: str = ""             # bystra
    setup: str = ""
    entry_pattern: str = ""
    confidence: float = 0.0
    direction: str = ""               # BUY | SELL
    entry: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    reason: str = ""
    trace_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self):
        return f"<ExecutionContract {self.contract_id} {self.action} {self.symbol} conf={self.confidence:.0%}>"
