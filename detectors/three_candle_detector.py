"""ThreeCandleDetector — CAPYBARS-style big-small-big compression pattern.

Pattern: C3(big) → C2(small/inside) → C1(big, same dir as C3)
- All 3 candles same direction (all bull or all bear)
- C2 body < C1 body * ratio AND C2 body < C3 body * ratio (compression)
- C2 high <= C1 high (bull) / C2 low >= C1 low (bear) — no breakout on middle
- Entry: limit at C2 zone (high/low of middle candle)
- SL: beyond C3 extreme, TP: nearest S/R
"""
from typing import Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    is_bullish, is_bearish, body_size, sl_buffer,
    htf_confirm_solid, find_nearest_support, find_nearest_resistance,
)

BODY_RATIO = 0.6  # C2 body must be < 60% of C1 and C3


class ThreeCandleDetector(BystraBaseDetector):
    """CAPYBARS-derived 3-candle compression entry detector."""

    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        # THREE_CANDLE not valid on M1 — too noisy
        if tf == "M1":
            return []
        candles = self._get_candles(context, tf, 30)
        if len(candles) < 5:
            return []

        htf_tf = "M15" if tf == "M5" else "H1"
        htf_candles = self._get_candles(context, htf_tf, 10)
        h1_candles = self._get_candles(context, "H1", 30)
        features = self._get_features(context)
        buf = sl_buffer(context)

        facts = []
        # candles[-1] = newest, scan recent bars only (last 10)
        for i in range(max(1, len(candles) - 10), len(candles) - 2):
            c3 = candles[i - 1]   # oldest of trio
            c2 = candles[i]       # middle (small)
            c1 = candles[i + 1]   # newest (big breakout)

            b1 = body_size(c1)
            b2 = body_size(c2)
            b3 = body_size(c3)

            if b1 == 0 or b3 == 0:
                continue

            # All 3 same direction
            if is_bullish(c3) and is_bullish(c2) and is_bullish(c1):
                direction = "BUY"
                # C2 no breakout above C3 (compression check)
                if float(c2.get("high", 0)) > float(c3.get("high", 0)):
                    continue
            elif is_bearish(c3) and is_bearish(c2) and is_bearish(c1):
                direction = "SELL"
                # C2 no breakout below C3 (compression check)
                if float(c2.get("low", 0)) < float(c3.get("low", 0)):
                    continue
            else:
                continue

            # C2 compression check
            if b2 >= b1 * BODY_RATIO or b2 >= b3 * BODY_RATIO:
                continue

            # Entry mode decision: immediate vs wait-retest-C2
            c2_high = float(c2.get("high", 0))
            c2_low = float(c2.get("low", 0))
            c1_strong = b1 > 1.5 * b3
            if c1_strong:
                entry_mode = "immediate"
                entry_zone = {
                    "high": float(c1.get("close", c1.get("high", 0))) + buf,
                    "low":  float(c1.get("close", c1.get("low",  0))) - buf,
                }
            else:
                entry_mode = "retest_c2"
                entry_zone = {"high": c2_high + buf, "low": c2_low - buf}

            # DZ for HTF confirm
            if features:
                dz_level = (features.get_nearest_resistance("H1") or c2_high * 1.05) \
                    if direction == "BUY" else \
                    (features.get_nearest_support("H1") or c2_low * 0.95)
            else:
                dz_level = find_nearest_resistance(candles, c2_high, h1_candles) \
                    if direction == "BUY" else \
                    find_nearest_support(candles, c2_low, h1_candles)

            if not htf_confirm_solid(htf_candles, direction, dz_level):
                # THREE_CANDLE has built-in 3-candle confirmation — skip htf_solid gate
                pass  # removed htf_confirm_solid block for THREE_CANDLE

            # SL beyond C3 extreme
            if direction == "BUY":
                sl = float(c3.get("low", 0)) - buf
                tp = (features.get_nearest_resistance("H1") if features else None) or \
                     find_nearest_resistance(candles, c1.get("high", 0), h1_candles)
            else:
                sl = float(c3.get("high", 0)) + buf
                tp = (features.get_nearest_support("H1") if features else None) or \
                     find_nearest_support(candles, c1.get("low", 0), h1_candles)

            facts.append(self._create_pattern_fact("THREE_CANDLE", 0.82, {
                "entry_zone": entry_zone,
                "entry_mode": entry_mode,
                "sl": float(sl),
                "tp": float(tp),
                "danger_zone": float(dz_level),
                "direction": direction,
                "entry_tf": tf,
                "detector_name": "ThreeCandleDetector",
            }))

        return facts
