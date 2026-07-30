"""TradeDecision — final output. Only place BUY/SELL/WAIT/SKIP allowed."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

BUY  = "BUY"
SELL = "SELL"
WAIT = "WAIT"
SKIP = "SKIP"


@dataclass
class TradeDecision:
    action: str                             # BUY | SELL | WAIT | SKIP
    setup_id: str = ""
    setup_name: str = ""
    confidence: float = 0.0
    reason: str = ""
    ranking: List[Dict[str, Any]] = field(default_factory=list)  # all candidates ranked
    trace: List[str] = field(default_factory=list)
    explanation: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<TradeDecision {self.action} setup={self.setup_id} conf={self.confidence:.0%}>"
