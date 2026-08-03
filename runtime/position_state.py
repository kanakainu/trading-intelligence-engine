"""PositionState — tracks one live position, updated by monitor each tick."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class PositionState:
    position_id: str
    symbol: str
    direction: str          # BUY | SELL
    entry_price: float
    current_price: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    volume: float
    open_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    comment: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Extended fields for TrailingManager
    strategy_id: str = "unknown"           # e.g., "bystra", "aggressive", "semi_hft"
    unrealized_profit: float = 0.0         # PnL in USD from broker
    rr: float = 0.0                        # Risk:Reward ratio
    sl_dist_pts: float = 0.0               # SL distance in points
    point_value: float = 0.1               # USD per point (symbol-specific)
    digits: int = 2                        # Symbol digits for rounding

    @property
    def profit_pts(self) -> float:
        direction = 1 if self.direction.upper() == "BUY" else -1
        return (self.current_price - self.entry_price) * direction

    @property
    def is_buy(self) -> bool:
        return self.direction.upper() == "BUY"
