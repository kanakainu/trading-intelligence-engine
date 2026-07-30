"""RuntimeEvents — position lifecycle event types for the runtime event bus."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict


class PositionEventType(Enum):
    POSITION_REGISTERED = "POSITION_REGISTERED"
    POSITION_BREAKEVEN   = "POSITION_BREAKEVEN"
    POSITION_TRAILING    = "POSITION_TRAILING"
    POSITION_PARTIAL_TP  = "POSITION_PARTIAL_TP"
    POSITION_CLOSED      = "POSITION_CLOSED"
    POSITION_MODIFIED    = "POSITION_MODIFIED"
    CIRCUIT_BREAKER      = "CIRCUIT_BREAKER"


@dataclass
class RuntimePositionEvent:
    event_type: PositionEventType
    position_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
