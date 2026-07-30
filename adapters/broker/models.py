"""Standardized broker data models — no trading logic."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class OrderRequest:
    symbol: str
    side: str                        # BUY | SELL
    volume: float
    order_type: str = "market"       # market | limit | stop
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    comment: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderResponse:
    order_id: str = ""
    status: str = ""                 # FILLED | REJECTED | PENDING
    filled_price: Optional[float] = None
    filled_volume: Optional[float] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None


@dataclass
class Position:
    position_id: str
    symbol: str
    side: str
    volume: float
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    unrealized_profit: float = 0.0
    open_time: Optional[datetime] = None


@dataclass
class AccountInfo:
    balance: float = 0.0
    equity: float = 0.0
    margin: float = 0.0
    free_margin: float = 0.0
    margin_level: float = 0.0
    currency: str = "USD"
    leverage: int = 1
