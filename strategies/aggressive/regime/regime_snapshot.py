"""Aggressive Regime Snapshot — classification output."""
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class AggressiveRegime(Enum):
    BULL = "bull"
    BEAR = "bear"
    MINOR_TREND = "minor_trend"
    FLAT = "flat"


@dataclass
class AggressiveRegimeSnapshot:
    regime: AggressiveRegime
    trend_score: float          # 0-1
    volatility_score: float     # 0-1
    liquidity_score: float      # 0-1
    confidence: float           # 0-1
    timestamp: datetime
