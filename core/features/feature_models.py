"""Feature Models — Namespaced FeatureSnapshot (Single Source of Truth)."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


# ============ NAMESPACES ============

@dataclass(frozen=True, slots=True)
class TrendFeatures:
    """Trend namespace: EMA stack, slopes, ADX, direction."""
    ema: Dict[str, Dict[str, float]]           # {'M5': {'ema8': ..., 'ema21': ...}, 'H1': {...}}
    ema_slope: Dict[str, Dict[str, float]]     # {'M5': {'ema21_slope': ..., 'ema50_slope': ...}}
    adx: Dict[str, float]                      # per TF
    trend_direction: Dict[str, int]            # per TF: 1=up, -1=down, 0=flat
    ema_ribbon: Dict[str, List[float]]         # per TF: [ema8, ema9, ema13, ema21, ema34, ema50, ema200]


@dataclass(frozen=True, slots=True)
class VolatilityFeatures:
    """Volatility namespace: ATR, true range, ATR%, regime flags."""
    atr: Dict[str, float]                      # per TF
    atr_percent: Dict[str, float]              # per TF
    true_range: Dict[str, float]               # per TF
    atr_expansion: Dict[str, float]            # per TF: atr / atr_ma
    volatility_regime: Dict[str, str]          # per TF: "low", "normal", "high", "extreme"


@dataclass(frozen=True, slots=True)
class StructureFeatures:
    """Market Structure namespace: swings, S/R, pivots, market bias."""
    last_swing_high: Dict[str, float]          # per TF
    last_swing_low: Dict[str, float]           # per TF
    supports: Dict[str, List[float]]           # per TF: [s1, s2, s3...]
    resistances: Dict[str, List[float]]        # per TF: [r1, r2, r3...]
    nearest_support: Dict[str, float]          # per TF
    nearest_resistance: Dict[str, float]       # per TF
    pivot_levels: Dict[str, Dict[str, float]]  # per TF: {'pivot': ..., 'r1': ..., 's1': ...}
    market_structure: Dict[str, str]           # per TF: "bullish", "bearish", "neutral"
    structure_strength: Dict[str, float]       # per TF: 0-1


@dataclass(frozen=True, slots=True)
class MomentumFeatures:
    """Momentum namespace: body/wick ratios, impulse, velocity."""
    body_ratio: Dict[str, float]               # per TF
    wick_ratio: Dict[str, float]               # per TF
    impulse_size: Dict[str, float]             # per TF
    momentum_score: Dict[str, float]           # per TF
    price_velocity: Dict[str, float]           # per TF
    pullback_quality: Dict[str, float]         # per TF: 0-1


@dataclass(frozen=True, slots=True)
class VolumeFeatures:
    """Volume namespace: MA, ratio, spikes, profile."""
    volume_ma: Dict[str, float]                # per TF
    volume_ratio: Dict[str, float]             # per TF: volume / volume_ma
    volume_spike: Dict[str, float]             # per TF
    volume_profile: Dict[str, Dict[str, float]]  # per TF: {'high_vol': ..., 'low_vol': ...}


@dataclass(frozen=True, slots=True)
class LiquidityFeatures:
    """Liquidity namespace: spread, tick speed, session quality."""
    spread: float                              # current
    tick_speed: float                          # ticks per second
    spread_quality: str                        # "tight", "normal", "wide", "extreme"
    session_quality: str                       # "optimal", "good", "poor", "dead"
    liquidity_score: float                     # 0-1 composite


@dataclass(frozen=True, slots=True)
class SessionFeatures:
    """Session namespace: time-based context."""
    current_session: str                       # "ASIA", "LONDON", "NY", "OVERLAP"
    session_progress: float                    # 0-1 within session
    session_volatility: Dict[str, float]       # per session avg ATR%
    session_volume: Dict[str, float]           # per session avg volume


@dataclass(frozen=True, slots=True)
class StatisticsFeatures:
    """Statistics namespace: raw values, computed once."""
    raw_atr: Dict[str, float]
    raw_ema: Dict[str, Dict[str, float]]
    raw_vwap: Dict[str, float]
    candle_count: Dict[str, int]


# ============ MAIN SNAPSHOT ============

@dataclass(frozen=True, slots=True)
class FeatureSnapshot:
    """
    Immutable feature snapshot — SINGLE SOURCE OF TRUTH.
    
    All namespaces computed ONCE per scan by FeatureEngine.
    No detector calculates EMA/ATR/VWAP/ADX/Slope/Spread/Tick.
    """
    # Identity
    symbol: str
    timestamp: datetime
    scan_id: str
    
    # Namespaces
    trend: TrendFeatures
    volatility: VolatilityFeatures
    structure: StructureFeatures
    momentum: MomentumFeatures
    volume: VolumeFeatures
    liquidity: LiquidityFeatures
    session: SessionFeatures
    statistics: StatisticsFeatures
    
    # Raw candles reference
    candles: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    
    # ============ CONVENIENCE ACCESSORS ============
    
    def get_ema(self, timeframe: str, period: int) -> Optional[float]:
        return self.trend.ema.get(timeframe, {}).get(f"ema{period}")
    
    def get_ema_slope(self, timeframe: str, period: int) -> Optional[float]:
        return self.trend.ema_slope.get(timeframe, {}).get(f"ema{period}_slope")
    
    def get_atr(self, timeframe: str) -> Optional[float]:
        return self.volatility.atr.get(timeframe)
    
    def get_vwap(self, timeframe: str) -> Optional[float]:
        return self.statistics.raw_vwap.get(timeframe)
    
    def get_swing_high(self, timeframe: str) -> Optional[float]:
        return self.structure.last_swing_high.get(timeframe)
    
    def get_swing_low(self, timeframe: str) -> Optional[float]:
        return self.structure.last_swing_low.get(timeframe)
    
    def get_nearest_support(self, timeframe: str) -> Optional[float]:
        return self.structure.nearest_support.get(timeframe)
    
    def get_nearest_resistance(self, timeframe: str) -> Optional[float]:
        return self.structure.nearest_resistance.get(timeframe)
    
    def get_adx(self, timeframe: str) -> Optional[float]:
        return self.trend.adx.get(timeframe)
    
    def get_liquidity_score(self) -> float:
        return self.liquidity.liquidity_score
    
    def get_momentum_score(self, timeframe: str) -> Optional[float]:
        return self.momentum.momentum_score.get(timeframe)
    
    def get_volume_ratio(self, timeframe: str) -> Optional[float]:
        return self.volume.volume_ratio.get(timeframe)
    
    def get_structure_strength(self, timeframe: str) -> Optional[float]:
        return self.structure.structure_strength.get(timeframe)


@dataclass(frozen=True, slots=True)
class FeatureInputs:
    """Raw inputs for feature computation."""
    candles: Dict[str, List[Dict[str, Any]]]  # M1, M5, M15, H1
    current_tick: Optional[Dict[str, Any]] = None
    spread: float = 0.0
    symbol: str = ""
    timestamp: Optional[datetime] = None
    scan_id: str = ""


# Backward compatibility aliases
FeatureSnapshot.get_swing = lambda self, tf, side: (
    self.get_swing_high(tf) if side == "high" else self.get_swing_low(tf)
)