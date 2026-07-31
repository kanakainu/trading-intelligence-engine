from typing import Dict, Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    get_base_zone, htf_confirm_solid, check_retest,
    is_bullish, is_bearish, danger_zone_touched, sl_buffer
)

class Hybrid1Detector(BystraBaseDetector):
    """HYBRID1: Reversal at RBR/DBD/QMR. MUST NOT touch Danger Zone."""
    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        candles = self._get_candles(context, tf, 20)
        if len(candles) < 5: return []

        features = self._get_features(context)
        h1_candles = self._get_candles(context, "H1", 30)

        for i in range(1, len(candles) - 2):
            prev, base, brk = candles[i-1], candles[i], candles[i+1]

            direction = ""
            if is_bullish(prev) and is_bullish(brk): direction = "BUY"
            elif is_bearish(prev) and is_bearish(brk): direction = "SELL"
            if not direction: continue

            base_zone = get_base_zone(candles, i)

            if direction == "BUY":
                dz_level = base_zone["low"]
                if any(danger_zone_touched(c, dz_level, "BUY") for c in candles[:-1]): continue
                if features:
                    sl_level = features.get_swing("tf", "low") or base_zone["low"]
                    sl = base_zone["low"] - sl_buffer(context)
                    tp = features.get_nearest_resistance("H1") or base_zone["high"] * 1.02
                else:
                    from detectors.common import find_swing_pivots, find_nearest_resistance
                    all_pivots = find_swing_pivots(candles)
                    sl_p = [p["price"] for p in all_pivots if p["type"] == "low" and p["price"] < base_zone["low"]]
                    sl = (max(sl_p) if sl_p else base_zone["low"]) - sl_buffer(context)
                    tp = find_nearest_resistance(candles, base_zone["high"], h1_candles)
            else:
                dz_level = base_zone["high"]
                if any(danger_zone_touched(c, dz_level, "SELL") for c in candles[:-1]): continue
                if features:
                    sl = base_zone["high"] + sl_buffer(context)
                    tp = features.get_nearest_support("H1") or base_zone["low"] * 0.98
                else:
                    from detectors.common import find_swing_pivots, find_nearest_support
                    all_pivots = find_swing_pivots(candles)
                    sl_p = [p["price"] for p in all_pivots if p["type"] == "high" and p["price"] > base_zone["high"]]
                    sl = (min(sl_p) if sl_p else base_zone["high"]) + sl_buffer(context)
                    tp = find_nearest_support(candles, base_zone["low"], h1_candles)

            htf_tf = "M15" if tf == "M5" else "H1"
            htf_candles = self._get_candles(context, htf_tf, 10)
            if not htf_confirm_solid(htf_candles, direction, dz_level): continue
            if not check_retest(candles, base_zone, direction): continue

            return [self._create_pattern_fact("HYBRID1", 0.85, {
                "entry_zone": {"high": base_zone["high"], "low": base_zone["low"]},
                "sl": float(sl), "tp": float(tp), "danger_zone": float(dz_level),
                "direction": direction, "entry_tf": tf, "detector_name": "Hybrid1Detector"
            })]
        return []
