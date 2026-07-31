"""Feature Models — Immutable FeatureSnapshot shared across all detectors."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


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

    # Trend (multi-TF EMA stack)
    ema: Dict[str, Dict[str, float]] = field(default_factory=dict)
    ema_slope: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Volatility
    atr: Dict[str, float] = field(default_factory=dict)
    atr_percent: Dict[str, float] = field(default_factory=dict)
    true_range: Dict[str, float] = field(default_factory=dict)

    # Momentum
    body_ratio: Dict[str, float] = field(default_factory=dict)
    wick_ratio: Dict[str, float] = field(default_factory=dict)
    impulse_size: Dict[str, float] = field(default_factory=dict)
    momentum_score: Dict[str, float] = field(default_factory=dict)

    # Volume
    volume_ma: Dict[str, float] = field(default_factory=dict)
    volume_ratio: Dict[str, float] = field(default_factory=dict)
    volume_spike: Dict[str, float] = field(default_factory=dict)

    # VWAP
    vwap: Dict[str, float] = field(default_factory=dict)
    distance_to_vwap: Dict[str, float] = field(default_factory=dict)

    # Market Microstructure
    spread: float = 0.0
    tick_speed: float = 0.0
    price_velocity: float = 0.0

    # Structure — swing pivots (Sprint B3.1)
    last_swing_high: Dict[str, float] = field(default_factory=dict)
    last_swing_low: Dict[str, float] = field(default_factory=dict)
    nearest_support: Dict[str, float] = field(default_factory=dict)     # new B3.1
    nearest_resistance: Dict[str, float] = field(default_factory=dict)  # new B3.1

    # Raw candles reference
    candles: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    # ── Accessors ──────────────────────────────────────────────────────────

    def get_ema(self, timeframe: str, period: int) -> Optional[float]:
        return self.ema.get(timeframe, {}).get(f"ema{period}")

    def get_ema_slope(self, timeframe: str, period: int) -> Optional[float]:
        return self.ema_slope.get(timeframe, {}).get(f"ema{period}_slope")

    def get_atr(self, timeframe: str) -> Optional[float]:
        return self.atr.get(timeframe)

    def get_vwap(self, timeframe: str) -> Optional[float]:
        return self.vwap.get(timeframe)

    def get_swing(self, timeframe: str, side: str) -> Optional[float]:
        if side == "high":
            return self.last_swing_high.get(timeframe)
        return self.last_swing_low.get(timeframe)

    def get_nearest_support(self, timeframe: str) -> Optional[float]:
        return self.nearest_support.get(timeframe)

    def get_nearest_resistance(self, timeframe: str) -> Optional[float]:
        return self.nearest_resistance.get(timeframe)


@dataclass(frozen=True, slots=True)
class FeatureInputs:
    """Raw inputs for feature computation."""
    candles: Dict[str, List[Dict[str, Any]]]
    current_tick: Optional[Dict[str, Any]] = None
    spread: float = 0.0
    symbol: str = ""
    timestamp: Optional[datetime] = None
    scan_id: str = ""
