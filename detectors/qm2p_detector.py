from typing import Dict, Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    htf_confirm_solid, find_nearest_support,
    find_nearest_resistance, find_swing_pivots, check_retest,
    is_bullish, is_bearish,
    sl_buffer,
)


class Qm2pDetector(BystraBaseDetector):
    """QM2P: Quasimodo 2-Point Trendline.
    QMR + 2-point trendline connecting same head.
    Standalone reversal setup — muncul dalam reversal trend.
    Struktur = QMR tapi level head sama (membentuk trendline di level yg sama).
    """

    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        candles = self._get_candles(context, tf, 40)
        if len(candles) < 15:
            return []

        pivots = find_swing_pivots(candles)
        if len(pivots) < 4:
            return []

        h1_candles = self._get_candles(context, "H1", 30)

        for i in range(4, len(pivots)):
            p4, p3, p2, p1, p0 = pivots[i - 4], pivots[i - 3], pivots[i - 2], pivots[i - 1], pivots[i]

            direction = ""
            head_price = 0.0
            entry_level = 0.0

            # W-shape BUY: Lower Low(L1) → Higher High(H1) → Equal/Similar Low(L2) → Higher High(H2)
            if p4["type"] == "low" and p3["type"] == "high" and p2["type"] == "low" \
                    and p1["type"] == "high":
                # QM2P specific: head (p2 and p4) must be at similar level
                head_diff = abs(p2["price"] - p4["price"]) / p4["price"]
                if head_diff > 0.002:  # Max 0.2% difference = similar head level
                    continue
                if p1["price"] <= p3["price"]:
                    continue  # Must be higher high
                direction = "BUY"
                entry_level = p4["price"]
                head_price = p2["price"]

            # M-shape SELL: Higher High(H1) → Lower Low(L1) → Equal/Similar High(H2) → Lower Low(L2)
            elif p4["type"] == "high" and p3["type"] == "low" and p2["type"] == "high" \
                    and p1["type"] == "low":
                head_diff = abs(p2["price"] - p4["price"]) / p4["price"]
                if head_diff > 0.002:
                    continue
                if p1["price"] >= p3["price"]:
                    continue
                direction = "SELL"
                entry_level = p4["price"]
                head_price = p2["price"]

            if not direction:
                continue

            base_zone = {"high": entry_level + 0.2, "low": entry_level - 0.2}

            # HTF confirmation mandatory
            htf_tf = "M15" if tf == "M5" else "H1"
            htf_candles = self._get_candles(context, htf_tf, 10)
            dz_level = find_nearest_resistance(candles, entry_level, h1_candles) if direction == "BUY" \
                else find_nearest_support(candles, entry_level, h1_candles)

            if not htf_confirm_solid(htf_candles, direction, dz_level):
                continue

            # Retest — price must return to left shoulder level
            if not check_retest(candles, base_zone, direction):
                continue

            # SL = beyond head (similar to QMR but now trendline is at same head level)
            _buf = sl_buffer(context)
            sl = head_price + _buf if direction == "SELL" else head_price - _buf
            # TP = nearest target beyond opposite shoulder
            tp = find_nearest_resistance(candles, p3["price"], h1_candles) if direction == "BUY" \
                else find_nearest_support(candles, p3["price"], h1_candles)

            return [self._create_pattern_fact("QM2P", 0.85, {
                "entry_zone": base_zone,
                "sl": float(sl),
                "tp": float(tp),
                "danger_zone": float(dz_level),
                "direction": direction,
                "entry_tf": tf,
                "head_trendline": True,
                "detector_name": "Qm2pDetector"
            })]

        return []