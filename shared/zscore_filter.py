"""Z-Score Filter — Goldman Sachs inspired overextension detection.

Detects when price is statistically overextended from its rolling mean:
- Z > +Z_MAX → price too high → BLOCK BUY (overextended on the upside)
- Z < -Z_MAX → price too low → BLOCK SELL (overextended on the downside)
- |Z| in normal range → allow

Toggle: config/features.json → zscore_filter: true/false
"""
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List

_FEATURES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "features.json")
WINDOW = 20  # Rolling window for mean/std
Z_MAX = 2.0  # Statistical extreme threshold (Tightened from 2.2)


def _load_config() -> dict:
    try:
        with open(_FEATURES_PATH) as f:
            return json.load(f)
    except Exception:
        return {"zscore_filter": True}


@dataclass
class ZScoreVerdict:
    allowed: bool
    reason: str
    z_score: float = 0.0


def check(features: Any, candles: Dict[str, List[dict]], direction: str) -> ZScoreVerdict:
    """
    Z-Score overextension check before entry.

    Args:
        features: FeatureSnapshot (unused, kept for interface parity)
        candles: Full-TF candle dict
        direction: "BUY" or "SELL"

    Returns:
        ZScoreVerdict(allowed, reason, z_score)
    """
    cfg = _load_config()
    if not cfg.get("zscore_filter", True):
        return ZScoreVerdict(True, "zscore_filter_disabled")

    m5 = candles.get("M5", [])
    if len(m5) < WINDOW + 1:
        return ZScoreVerdict(True, "insufficient_candles_skip")

    closes = [float(c.get("close", 0)) for c in m5[-WINDOW:]]
    if len(closes) < WINDOW:
        return ZScoreVerdict(True, "insufficient_data_skip")

    mean = sum(closes) / len(closes)
    variance = sum((c - mean) ** 2 for c in closes) / len(closes)
    std = variance ** 0.5

    if std <= 0:
        return ZScoreVerdict(True, "flat_market_skip")

    price = closes[-1]
    z = (price - mean) / std

    if direction == "BUY" and z > Z_MAX:
        return ZScoreVerdict(False, f"zscore_overextended_buy_blocked z={z:.2f} (max={Z_MAX})", z)
    if direction == "SELL" and z < -Z_MAX:
        return ZScoreVerdict(False, f"zscore_overextended_sell_blocked z={z:.2f} (max={Z_MAX})", z)

    return ZScoreVerdict(True, f"zscore_ok z={z:.2f}", z)
