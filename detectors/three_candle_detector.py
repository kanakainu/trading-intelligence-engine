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
        if tf != "M5":
            return []
            
        candles = self._get_candles(context, tf, 30)
        # M15 Trend Check: 3 of last 5 must be same dir
        m15_candles = self._get_candles(context, "M15", 10)
        if len(candles) < 5 or len(m15_candles) < 6:
            return []

        m15_bull = sum(1 for c in m15_candles[-6:-1] if is_bullish(c))
        m15_bear = sum(1 for c in m15_candles[-6:-1] if is_bearish(c))
        m15_trend = "BULL" if m15_bull >= 3 else "BEAR" if m15_bear >= 3 else "NONE"

        facts = []
        closed = candles[:-1]
        for i in range(max(2, len(closed) - 5), len(closed)):
            c3, c2, c1 = closed[i-2], closed[i-1], closed[i]
            
            # All 3 same direction
            if is_bullish(c3) and is_bullish(c2) and is_bullish(c1):
                if m15_trend != "BULL": continue
                direction = "BUY"
                # C2 inside C3 range
                if float(c2["high"]) > float(c3["high"]) or float(c2["low"]) < float(c3["low"]): continue
            elif is_bearish(c3) and is_bearish(c2) and is_bearish(c1):
                if m15_trend != "BEAR": continue
                direction = "SELL"
                # C2 inside C3 range
                if float(c2["low"]) < float(c3["low"]) or float(c2["high"]) > float(c3["high"]): continue
            else:
                continue

            # Compression check
            b1, b2, b3 = body_size(c1), body_size(c2), body_size(c3)
            if b2 >= b1 * 0.3 or b2 >= b3 * 0.3: continue

            facts.append(self._create_pattern_fact("THREE_CANDLE", 0.85, {
                "direction": direction,
                "c1": c1, "c2": c2, "c3": c3,
                "sl": float(c3["low"] if direction=="BUY" else c3["high"]),
                "cutloss": float(c2["low"] if direction=="BUY" else c2["high"])
            }))
        return facts
