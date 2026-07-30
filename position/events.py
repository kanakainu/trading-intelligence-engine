"""Position event types — integrate with Runtime event system."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict


class PositionEventType(str, Enum):
    POSITION_OPENED            = "POSITION_OPENED"
    POSITION_UPDATED           = "POSITION_UPDATED"
    POSITION_PARTIALLY_CLOSED  = "POSITION_PARTIALLY_CLOSED"
    POSITION_CLOSED            = "POSITION_CLOSED"
    POSITION_SYNCED            = "POSITION_SYNCED"
    POSITION_ERROR             = "POSITION_ERROR"


@dataclass
class PositionEvent:
    event_type: PositionEventType
    position_id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
