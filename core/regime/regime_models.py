"""Regime Models — Immutable RegimeSnapshot with classification enums."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional
from datetime import datetime


class Regime(Enum):
    """Market regime classification — ordered by trend strength."""
    UNKNOWN = 0
    RANGE = 1          # Sideways, low ATR, flat EMAs
    CHOPPY = 2         # Sideways, high ATR, whipsaws
    EARLY_TREND = 3    # Emerging trend, ADX rising
    TRENDING = 4       # Clear trend, ADX > 25
    STRONG_TREND = 5   # Powerful trend, ADX > 40
    EXHAUSTION = 6     # Trend overextended, divergence
    NEWS = 7           # High volatility, spread spike, news-driven
    LOW_LIQUIDITY = 8  # Thin volume, wide spreads, Asian session


class TrendDirection(Enum):
    """Trend direction within a regime."""
    FLAT = 0
    UP = 1
    DOWN = -1


@dataclass(frozen=True, slots=True)
class RegimeSnapshot:
    """
    Immutable regime classification result.
    Pure classification — NO strategy logic.
    """
    # Primary classification
    regime: Regime
    trend_direction: TrendDirection
    confidence: float  # 0.0 - 1.0

    # Component scores (for transparency/debugging)
    adx_score: float = 0.0          # 0-1: trend strength
    ema_slope_score: float = 0.0    # 0-1: EMA alignment
    atr_expansion_score: float = 0.0  # 0-1: volatility regime
    vwap_distance_score: float = 0.0  # 0-1: mean reversion pressure
    volume_score: float = 0.0       # 0-1: participation

    # Raw values used
    adx: float = 0.0
    ema_slope: float = 0.0
    atr_pct: float = 0.0
    vwap_distance: float = 0.0
    volume_ratio: float = 0.0

    # Metadata
    symbol: str = ""
    timeframe: str = "H1"
    timestamp: datetime = field(default_factory=datetime.now)
    scan_id: str = ""

    def is_trending(self) -> bool:
        """True if regime is trending or stronger."""
        return self.regime.value >= Regime.EARLY_TREND.value

    def is_range(self) -> bool:
        """True if regime is range-bound."""
        return self.regime in (Regime.RANGE, Regime.CHOPPY)

    def is_extreme(self) -> bool:
        """True if regime is exhaustion, news, or low liquidity."""
        return self.regime in (Regime.EXHAUSTION, Regime.NEWS, Regime.LOW_LIQUIDITY)

    def to_dict(self) -> Dict:
        return {
            "regime": self.regime.name,
            "trend_direction": self.trend_direction.name,
            "confidence": round(self.confidence, 3),
            "adx": round(self.adx, 2),
            "ema_slope": round(self.ema_slope, 5),
            "atr_pct": round(self.atr_pct, 4),
            "vwap_distance": round(self.vwap_distance, 2),
            "volume_ratio": round(self.volume_ratio, 2),
            "scores": {
                "adx": round(self.adx_score, 3),
                "ema_slope": round(self.ema_slope_score, 3),
                "atr_expansion": round(self.atr_expansion_score, 3),
                "vwap_distance": round(self.vwap_distance_score, 3),
                "volume": round(self.volume_score, 3),
            }
        }


@dataclass(frozen=True, slots=True)
class RegimeInputs:
    """Inputs required for regime classification."""
    # From FeatureSnapshot
    ema: Dict[str, Dict[str, float]]  # e.g., {"H1": {"ema21": ..., "ema50": ...}}
    ema_slope: Dict[str, Dict[str, float]]
    atr: Dict[str, float]
    atr_percent: Dict[str, float]
    true_range: Dict[str, float]
    vwap: Dict[str, float]
    distance_to_vwap: Dict[str, float]
    volume_ratio: Dict[str, float]
    volume_spike: Dict[str, float]
    momentum_score: Dict[str, float]
    spread: float
    tick_speed: float
    price_velocity: float

    symbol: str
    timeframe: str = "H1"
    timestamp: Optional[datetime] = None
    scan_id: str = ""
    current_price: float = 0.0  # For VWAP distance normalization