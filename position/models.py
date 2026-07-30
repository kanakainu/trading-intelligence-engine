"""Position data models — provider-agnostic position representation."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional


class PositionStatus(str, Enum):
    CREATED            = "CREATED"
    SUBMITTED          = "SUBMITTED"
    OPEN               = "OPEN"
    PARTIALLY_CLOSED   = "PARTIALLY_CLOSED"
    MODIFIED           = "MODIFIED"
    CLOSING            = "CLOSING"
    CLOSED             = "CLOSED"
    REJECTED           = "REJECTED"
    ERROR              = "ERROR"


@dataclass
class Position:
    position_id: str = ""
    order_id: str = ""
    symbol: str = ""
    side: str = ""             # BUY / SELL
    volume: float = 0.0
    entry_price: Decimal = Decimal("0")
    current_price: Decimal = Decimal("0")
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    status: PositionStatus = PositionStatus.CREATED
    opened_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PositionAuditEntry:
    position_id: str = ""
    previous_status: Optional[str] = None
    current_status: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""
    notes: str = ""


@dataclass
class PositionHealth:
    active_positions: int = 0
    closed_positions: int = 0
    synchronization_status: str = "UNKNOWN"
    last_sync: Optional[datetime] = None
    status: str = "UNKNOWN"
    errors: int = 0
