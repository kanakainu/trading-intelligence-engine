"""Feature Engine Package — Shared computed features for all detectors.

Usage:
    from core.features import compute_features, FeatureInputs
    from core.features.feature_models import FeatureSnapshot

    inputs = FeatureInputs(
        candles={"M5": [...], "M15": [...], "H1": [...]},
        current_tick=tick_data,
        spread=spread,
        symbol="XAUUSD",
        timestamp=datetime.now()
    )
    features = compute_features(inputs)

    # In detector:
    ema21 = features.get_ema("M5", 21)
    atr = features.get_atr("M5")
    vwap = features.get_vwap("M5")
    swing_high = features.get_swing("M5", "high")
"""
from core.features.feature_models import FeatureSnapshot, FeatureInputs
from core.features.feature_engine import FeatureEngine
from core.features.feature_cache import FeatureCache, get_feature_cache, compute_features

__all__ = [
    "FeatureSnapshot",
    "FeatureInputs",
    "FeatureEngine",
    "FeatureCache",
    "get_feature_cache",
    "compute_features",
]

__version__ = "1.0.0"