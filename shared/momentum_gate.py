"""Momentum Gate — confirm candle is actively moving before entry.

Checks last closed M5 candle:
- body_size > ATR_M5 * MIN_BODY_RATIO  (candle has real push)
- close confirms direction (BUY: close > open, SELL: close < open)

THREE_CANDLE exempt — pattern already encodes momentum.
"""
from dataclasses import dataclass
from typing import Any, Dict, List


MIN_BODY_RATIO = 0.4  # candle body must be >= 40% of ATR M5


@dataclass
class MomentumVerdict:
    allowed: bool
    reason: str


def check(features: Any, candles: Dict[str, List[dict]], direction: str, setup_name: str = "") -> MomentumVerdict:
    # THREE_CANDLE exempt — pattern already encodes momentum
    if "THREE_CANDLE" in setup_name.upper():
        return MomentumVerdict(True, "three_candle_exempt")
    # M5 Mean Reversion exempt — reversal by definition goes against last candle
    if "MR_" in setup_name.upper() or "MEAN_REV" in setup_name.upper():
        return MomentumVerdict(True, "mr_exempt")
    m5 = candles.get("M5", [])
    if len(m5) < 2:
        return MomentumVerdict(True, "no_candles_skip")

    # Use second-to-last candle (last fully closed)
    c = m5[-2]
    o = float(c.get("open", 0))
    cl = float(c.get("close", 0))
    body = abs(cl - o)

    atr = 0.0
    if hasattr(features, "atr") and isinstance(features.atr, dict):
        atr = float(features.atr.get("M5", 0.0))

    if atr <= 0:
        return MomentumVerdict(True, "no_atr_skip")

    min_body = atr * MIN_BODY_RATIO

    if body < min_body:
        return MomentumVerdict(False, f"momentum_weak body={body:.2f} < {min_body:.2f} ({MIN_BODY_RATIO}x ATR)")

    if direction == "BUY" and cl <= o:
        return MomentumVerdict(False, f"momentum_conflict BUY but candle bearish (o={o:.2f} c={cl:.2f})")
    if direction == "SELL" and cl >= o:
        return MomentumVerdict(False, f"momentum_conflict SELL but candle bullish (o={o:.2f} c={cl:.2f})")

    return MomentumVerdict(True, f"momentum_ok body={body:.2f} atr={atr:.2f}")
