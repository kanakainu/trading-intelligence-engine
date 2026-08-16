from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional

@dataclass(frozen=True, slots=True)
class FeatureSnapshot:
    """
    Immutable feature snapshot computed once per scan.
    All detectors read from this — NO detector calculates EMA/ATR/VWAP.
    """
    # Metadata
    symbol: str
    timestamp: datetime
    scan_id: str

    # Current Market State
    current_price: float = 0.0
    spread: float = 0.0
    
    # Account Info
    balance: float = 0.0
    equity: float = 0.0
    open_positions: int = 0
    raw_positions: list = field(default_factory=list)

    # Indicator Data (multi-TF)
    ema: Dict[str, Dict[str, float]] = field(default_factory=dict)
    ema_slope: Dict[str, Dict[str, float]] = field(default_factory=dict)
    atr: Dict[str, float] = field(default_factory=dict)
    atr_percent: Dict[str, float] = field(default_factory=dict)
    true_range: Dict[str, float] = field(default_factory=dict)
    body_ratio: Dict[str, float] = field(default_factory=dict)
    wick_ratio: Dict[str, float] = field(default_factory=dict)
    impulse_size: Dict[str, float] = field(default_factory=dict)
    momentum_score: Dict[str, float] = field(default_factory=dict)
    volume_ma: Dict[str, float] = field(default_factory=dict)
    volume_ratio: Dict[str, float] = field(default_factory=dict)
    volume_spike: Dict[str, float] = field(default_factory=dict)
    vwap: Dict[str, float] = field(default_factory=dict)
    distance_to_vwap: Dict[str, float] = field(default_factory=dict)

    # Structure — swing pivots & S/R
    last_swing_high: Dict[str, float] = field(default_factory=dict)
    last_swing_low: Dict[str, float] = field(default_factory=dict)
    nearest_support: Dict[str, float] = field(default_factory=dict)
    nearest_resistance: Dict[str, float] = field(default_factory=dict)

    # Raw candles reference
    candles: Dict[str, list] = field(default_factory=dict)

    # ── Accessors ──────────────────────────────────────────────────────────
    def get_atr(self, tf: str) -> float:
        return self.atr.get(tf, 0.0)

    def get_ema(self, tf: str, period: int) -> float:
        return self.ema.get(tf, {}).get(f"ema{period}", 0.0)

    def get_ema_slope(self, tf: str, period: int) -> float:
        return self.ema_slope.get(tf, {}).get(f"ema{period}_slope", 0.0)

    def get_momentum_score(self, tf: str) -> float:
        return self.momentum_score.get(tf, 0.0)

    def get_volume_ratio(self, tf: str) -> float:
        return self.volume_ratio.get(tf, 0.0)

    def get_vwap(self, tf: str) -> float:
        return self.vwap.get(tf, 0.0)

    def get_vwap_distance(self, tf: str) -> float:
        return self.distance_to_vwap.get(tf, 0.0)

    def get_swing(self, tf: str, type: str) -> Optional[float]:
        if type == "high": return self.last_swing_high.get(tf)
        if type == "low":  return self.last_swing_low.get(tf)
        return None

    def get_sr(self, tf: str, type: str) -> Optional[float]:
        if type == "support":    return self.nearest_support.get(tf)
        if type == "resistance": return self.nearest_resistance.get(tf)
        return None


@dataclass(frozen=True, slots=True)
class FeatureInputs:
    """Raw inputs for feature computation."""
    candles: Dict[str, List[Dict[str, Any]]]
    current_tick: Optional[Dict[str, Any]] = None
    spread: float = 0.0
    symbol: str = ""
    timestamp: Optional[datetime] = None
    scan_id: str = ""
    balance: float = 0.0  # New
    equity: float = 0.0    # New
    open_positions: int = 0 # New
    raw_positions: list = field(default_factory=list) # New
    current_price: float = 0.0 # New (Pass actual price from broker)
