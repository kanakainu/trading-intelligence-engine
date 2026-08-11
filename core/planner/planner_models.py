"""Trade Plan Models — TradePlan output from Trade Planner."""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass(frozen=True, slots=True)
class TradePlan:
    """
    Immutable trade plan — Entry + SL + TP + DZ + RR + Position Spec.
    
    Output of Trade Planner.
    NO execution logic.
    """
    # Identity
    plan_id: str
    symbol: str
    direction: str  # "buy", "sell"
    
    # Entry
    entry_zone: Dict[str, float]  # {"low": ..., "high": ...}
    entry_mid: float
    
    # Risk Management
    sl: Optional[float]
    tp: Optional[float]
    danger_zone: Optional[float]
    
    # Risk Metrics
    risk_reward: float  # Actual RR ratio
    risk_points: float  # |SL - entry|
    reward_points: float  # |TP - entry|
    
    # Position Sizing
    position_size: float  # Lot size
    position_risk_pct: float  # % of balance risked
    
    # Context
    timeframe: str
    strategy: str
    confidence: float
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_zone": self.entry_zone,
            "entry_mid": self.entry_mid,
            "sl": self.sl,
            "tp": self.tp,
            "danger_zone": self.danger_zone,
            "risk_reward": round(self.risk_reward, 2),
            "risk_points": round(self.risk_points, 2),
            "reward_points": round(self.reward_points, 2),
            "position_size": round(self.position_size, 2),
            "position_risk_pct": round(self.position_risk_pct, 2),
            "timeframe": self.timeframe,
            "strategy": self.strategy,
            "confidence": round(self.confidence, 3),
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class PlannerInputs:
    """Inputs for Trade Planner."""
    # From FusedSignal
    symbol: str
    direction: str
    entry_zone: Dict[str, float]
    confidence: float
    strategies: list[str]
    timeframe: str
    
    # Market Context
    h1_support: Optional[float] = None
    h1_resistance: Optional[float] = None
    detector_danger_zone: Optional[float] = None
    detector_sl: Optional[float] = None
    
    # Candles for swing pivot detection
    candles: Dict[str, list[Dict]] = field(default_factory=dict)
    
    # Risk params
    spread_buffer: float = 0.5
    atr: float = 5.0
    balance: float = 1000.0
    risk_per_trade_pct: float = 1.0  # 1% of balance
    current_price: float = 0.0 # Added for safety fallback in entry_mid calculation
    
    # Metadata
    scan_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)