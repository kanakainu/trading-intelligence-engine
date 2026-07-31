"""Aggressive Regime Snapshot — classification output."""
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class AggressiveRegime(Enum):
    TRENDING_BULL = "trending_bull"
    TRENDING_BEAR = "trending_bear"
    WEAK_TREND = "weak_trend"
    RANGING = "ranging"
    CHOPPY = "choppy"
    HIGH_VOLATILITY = "high_volatility"
    LOW_LIQUIDITY = "low_liquidity"


@dataclass
class AggressiveRegimeSnapshot:
    regime: AggressiveRegime
    trend_score: float          # 0-1
    volatility_score: float     # 0-1
    liquidity_score: float      # 0-1
    confidence: float           # 0-1
    timestamp: datetime
