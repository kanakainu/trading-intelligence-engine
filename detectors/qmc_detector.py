from typing import Dict, Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    get_base_zone, htf_confirm_solid, find_nearest_support,
    find_nearest_resistance, find_swing_pivots, check_retest,
    is_bullish, is_bearish, body_size,
    sl_buffer,
)


class QmcDetector(BystraBaseDetector):
    """QMC: Quasimodo Continuation.
    Continuation pattern — fresh reversal + trendline align.
    Entry sebaiknya dilakukan setelah reversal terjadi (fresh).
    Only valid in continuation trend (trendline align).
    """

    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        candles = self._get_candles(context, tf, 40)
        if len(candles) < 15:
            return []

        pivots = self._get_pivots(candles)
        if len(pivots) < 4:
            return []

        trendline_bull = context.metadata.get("trendline_bullish", False)
        trendline_bear = context.metadata.get("trendline_bearish", False)

        h1_candles = self._get_candles(context, "H1", 30)

        for i in range(4, len(pivots)):
            p4, p3, p2, p1, p0 = pivots[i - 4], pivots[i - 3], pivots[i - 2], pivots[i - 1], pivots[i]

            direction = ""
            entry_level = 0.0

            # W-shape BUY (continuation in uptrend)
            if p4["type"] == "low" and p3["type"] == "high" and p2["type"] == "low" \
                    and p1["type"] == "high" and p2["price"] < p4["price"] and p1["price"] > p3["price"]:
                if not trendline_bull:
                    continue  # QMC only valid with trendline align
                direction = "BUY"
                entry_level = p4["price"]

            # M-shape SELL (continuation in downtrend)
            elif p4["type"] == "high" and p3["type"] == "low" and p2["type"] == "high" \
                    and p1["type"] == "low" and p2["price"] > p4["price"] and p1["price"] < p3["price"]:
                if not trendline_bear:
                    continue
                direction = "SELL"
                entry_level = p4["price"]

            if not direction:
                continue

            # QMC specific: ensure this is continuation (trend same as direction)
            # Head (p2) must be opposite to entry for continuation pressure
            if direction == "BUY" and p1["price"] <= p3["price"]:
                continue
            if direction == "SELL" and p1["price"] >= p3["price"]:
                continue

            # Base zone at left shoulder level — use sl_buffer, not hardcoded 0.2
            _buf0 = sl_buffer(context)
            base_zone = {"high": entry_level + _buf0, "low": entry_level - _buf0}

            # HTF confirmation mandatory (M15 or H1)
            htf_tf = "M15" if tf == "M5" else "H1"
            htf_candles = self._get_candles(context, htf_tf, 10)
            dz_level = find_nearest_resistance(candles, entry_level, h1_candles) if direction == "BUY" \
                else find_nearest_support(candles, entry_level, h1_candles)

            if not htf_confirm_solid(htf_candles, direction, dz_level):
                continue

            # Retest check — price must return to base zone
            if not check_retest(candles, base_zone, direction):
                continue

            # SL = beyond head (p2), TP = nearest target in trend direction
            _buf = sl_buffer(context)
            sl = p2["price"] + _buf if direction == "SELL" else p2["price"] - _buf
            tp = find_nearest_resistance(candles, p1["price"], h1_candles) if direction == "BUY" \
                else find_nearest_support(candles, p1["price"], h1_candles)

            return [self._create_pattern_fact("QMC", 0.85, {
                "entry_zone": base_zone,
                "sl": float(sl),
                "tp": float(tp),
                "danger_zone": float(dz_level),
                "direction": direction,
                "entry_tf": tf,
                "detector_name": "QmcDetector"
            })]

        return []