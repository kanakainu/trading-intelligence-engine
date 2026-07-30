"""Market data models — standardized across all providers."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from decimal import Decimal


@dataclass
class Tick:
    symbol: str
    bid: Decimal
    ask: Decimal
    spread: Decimal
    timestamp: datetime
    volume: Optional[Decimal] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def mid(self) -> Decimal:
        return (self.bid + self.ask) / Decimal('2')


@dataclass
class Candle:
    symbol: str
    timeframe: str          # M1, M5, M15, M30, H1, H4, D1
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    timestamp: datetime
    spread: Optional[Decimal] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketSnapshot:
    symbol: str
    last_price: Decimal
    spread: Decimal
    volatility: Optional[Decimal] = None
    session: str = ""       # asian, london, new_york, overlap
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthReport:
    provider: str
    status: str             # CONNECTED | DISCONNECTED | ERROR
    connected: bool
    subscriptions: list
    latency_ms: float
    last_tick: str          # ISO timestamp
    error: str = None