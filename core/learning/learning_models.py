"""Learning Models — Post-trade reflection and analytics."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime


class TradeOutcome(Enum):
    """Trade result classification."""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    TIMEOUT = "timeout"


class ExitReason(Enum):
    """Why the trade closed."""
    TP_HIT = "tp_hit"
    SL_HIT = "sl_hit"
    MANUAL = "manual"
    TIMEOUT = "timeout"
    DANGER_ZONE = "danger_zone"
    TRAILING_STOP = "trailing_stop"
    PARTIAL_CLOSE = "partial_close"


@dataclass(frozen=True, slots=True)
class TradeReflection:
    """Immutable post-trade reflection for learning."""
    # Identity
    reflection_id: str
    trade_id: str
    symbol: str
    strategy: str
    
    # Outcome
    outcome: TradeOutcome
    exit_reason: ExitReason
    
    # P&L
    realized_pl: float
    realized_pl_pct: float
    risk_amount: float
    rr_actual: float  # Actual RR achieved
    rr_planned: float  # Planned RR from TradePlan
    
    # Timing
    duration_seconds: float
    entry_time: datetime
    exit_time: datetime
    
    # Entry Context
    entry_regime: str
    entry_confidence: float
    opportunity_priority: int
    
    # Exit Context
    exit_regime: str
    exit_price: float
    entry_price: float
    sl_price: Optional[float]
    tp_price: Optional[float]
    
    # Performance Metrics
    max_favorable_excursion: float  # MFE (max profit during trade)
    max_adverse_excursion: float   # MAE (max loss during trade)
    efficiency: float  # realized_pl / MFE (how much of potential captured)
    
    # Feature Context (snapshot at entry)
    entry_features: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "reflection_id": self.reflection_id,
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "strategy": self.strategy,
            "outcome": self.outcome.value,
            "exit_reason": self.exit_reason.value,
            "realized_pl": round(self.realized_pl, 2),
            "realized_pl_pct": round(self.realized_pl_pct, 2),
            "risk_amount": round(self.risk_amount, 2),
            "rr_actual": round(self.rr_actual, 2),
            "rr_planned": round(self.rr_planned, 2),
            "duration_seconds": self.duration_seconds,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat(),
            "entry_regime": self.entry_regime,
            "entry_confidence": round(self.entry_confidence, 3),
            "opportunity_priority": self.opportunity_priority,
            "exit_regime": self.exit_regime,
            "exit_price": self.exit_price,
            "entry_price": self.entry_price,
            "sl_price": self.sl_price,
            "tp_price": self.tp_price,
            "max_favorable_excursion": round(self.max_favorable_excursion, 2),
            "max_adverse_excursion": round(self.max_adverse_excursion, 2),
            "efficiency": round(self.efficiency, 2),
            "entry_features": self.entry_features,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    """Aggregate performance metrics."""
    # Sample stats
    total_trades: int
    win_count: int
    loss_count: int
    breakeven_count: int
    
    # Win rate
    win_rate: float
    
    # P&L
    total_pl: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    
    # Risk metrics
    avg_rr_actual: float
    avg_rr_planned: float
    avg_efficiency: float
    
    # Timing
    avg_duration_seconds: float
    
    # Strategy breakdown
    strategy_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Regime breakdown
    regime_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Metadata
    period_start: datetime = field(default_factory=datetime.now)
    period_end: datetime = field(default_factory=datetime.now)