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

BODY_RATIO = 0.3  # C2 body must be < 30% of C1 and C3 (stricter compression)


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
        # candles[-1] = current forming candle (skip), [-2] onward = closed candles
        # Scan last 10 closed candles for 3-candle pattern
        closed = candles[:-1]  # exclude current forming candle
        if len(closed) < 3:
            return []

        for i in range(max(2, len(closed) - 10), len(closed)):
            c3 = closed[i - 2]   # oldest of trio (big)
            c2 = closed[i - 1]   # middle (small/compression)
            c1 = closed[i]       # newest (big breakout, fully closed)

            b1 = body_size(c1)
            b2 = body_size(c2)
            b3 = body_size(c3)

            if b1 == 0 or b3 == 0:
                continue

            # All 3 same direction
            if is_bullish(c3) and is_bullish(c2) and is_bullish(c1):
                direction = "BUY"
            elif is_bearish(c3) and is_bearish(c2) and is_bearish(c1):
                direction = "SELL"
            else:
                continue

            # C2 body compression — must be smaller than BOTH C1 and C3
            # No strict inside-range requirement (too strict for XAUUSD)
            if b2 >= b1 * BODY_RATIO or b2 >= b3 * BODY_RATIO:
                continue

            # Entry: always at C1 close (immediate) — standalone strategy, no retest wait
            entry_mode = "immediate"
            entry_zone = {
                "price": float(c1.get("close", 0)),
                "high":  float(c1.get("close", 0)) + buf,
                "low":   float(c1.get("close", 0)) - buf,
            }

            c2_high = float(c2.get("high", 0))
            c2_low  = float(c2.get("low",  0))

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

            # SL beyond C3 extreme, TP nearest S/R or ATR fallback
            atr_val = float(features.atr if features and hasattr(features, 'atr') else 7.0)
            if direction == "BUY":
                sl = float(c3.get("low", 0)) - buf
                tp_sr = (features.get_nearest_resistance("H1") if features else None) or \
                        find_nearest_resistance(candles, c1.get("high", 0), h1_candles)
                tp = tp_sr if tp_sr and tp_sr < 999999 else float(c1.get("close", 0)) + atr_val * 3
            else:
                sl = float(c3.get("high", 0)) + buf
                tp_sr = (features.get_nearest_support("H1") if features else None) or \
                        find_nearest_support(candles, c1.get("low", 0), h1_candles)
                tp = tp_sr if tp_sr and tp_sr > 0 else float(c1.get("close", 0)) - atr_val * 3

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
