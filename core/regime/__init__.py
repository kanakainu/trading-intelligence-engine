"""Regime Engine Package — Market regime classification.

Usage:
    from core.regime import classify_regime, RegimeInputs
    from core.regime.regime_models import Regime, RegimeSnapshot

    inputs = RegimeInputs(
        ema=features.ema,
        ema_slope=features.ema_slope,
        atr=features.atr,
        atr_percent=features.atr_percent,
        true_range=features.true_range,
        vwap=features.vwap,
        distance_to_vwap=features.distance_to_vwap,
        volume_ratio=features.volume_ratio,
        volume_spike=features.volume_spike,
        momentum_score=features.momentum_score,
        spread=features.spread,
        tick_speed=features.tick_speed,
        price_velocity=features.price_velocity,
        symbol="XAUUSD",
        timeframe="H1",
        timestamp=datetime.now(),
        scan_id=features.scan_id
    )
    regime = classify_regime(inputs)

    print(regime.regime.name)  # RANGE, TRENDING, STRONG_TREND, etc.
    print(regime.trend_direction.name)  # UP, DOWN, FLAT
    print(regime.confidence)
    print(regime.to_dict())
"""
from core.regime.regime_models import (
    Regime,
    TrendDirection,
    RegimeSnapshot,
    RegimeInputs,
)
from core.regime.regime_engine import (
    RegimeEngine,
    get_regime_engine,
    classify_regime,
)

__all__ = [
    "Regime",
    "TrendDirection",
    "RegimeSnapshot",
    "RegimeInputs",
    "RegimeEngine",
    "get_regime_engine",
    "classify_regime",
]

__version__ = "1.0.0"