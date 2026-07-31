from typing import Dict, Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    get_base_zone, htf_confirm_solid, check_retest,
    is_bullish, is_bearish, body_size, sl_buffer
)

class Snrc3Detector(BystraBaseDetector):
    """SNRC3: Engulfing pattern at S/R zones."""
    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        candles = self._get_candles(context, tf, 20)
        if len(candles) < 5: return []

        features = self._get_features(context)

        for i in range(1, len(candles) - 2):
            prev, base, brk = candles[i-1], candles[i], candles[i+1]

            direction = ""
            is_eng = False
            if is_bearish(brk) and body_size(brk) > body_size(base) and is_bearish(base):
                direction = "BUY"; is_eng = True
            elif is_bullish(brk) and body_size(brk) > body_size(base) and is_bullish(base):
                direction = "SELL"; is_eng = True
            if not is_eng: continue

            base_zone = get_base_zone(candles, i)

            htf_tf = "M15" if tf == "M5" else "H1"
            htf_candles = self._get_candles(context, htf_tf, 10)
            h1_candles = self._get_candles(context, "H1", 30)

            # Danger Zone
            if features:
                if direction == "BUY":
                    dz_level = features.get_nearest_resistance("H1") or base_zone["high"] * 1.05
                else:
                    dz_level = features.get_nearest_support("H1") or base_zone["low"] * 0.95
            else:
                from detectors.common import find_nearest_support, find_nearest_resistance
                if direction == "BUY":
                    dz_level = find_nearest_resistance(candles, base_zone["high"], h1_candles)
                    if dz_level >= 999999.0: dz_level = base_zone["high"] * 1.05
                else:
                    dz_level = find_nearest_support(candles, base_zone["low"], h1_candles)
                    if dz_level <= 0: dz_level = base_zone["low"] * 0.95

            if not htf_confirm_solid(htf_candles, direction, dz_level): continue
            if not check_retest(candles, base_zone, direction): continue

            # SL/TP
            if features:
                sl = base_zone["low"] - 0.5 if direction == "BUY" else base_zone["high"] + 0.5
                tp = features.get_nearest_resistance("H1") or base_zone["high"] * 1.02 if direction == "BUY" else \
                     features.get_nearest_support("H1") or base_zone["low"] * 0.98
            else:
                from detectors.common import find_swing_pivots, find_nearest_support, find_nearest_resistance
                all_pivots = find_swing_pivots(candles)
                if direction == "BUY":
                    sl_pivot = [p["price"] for p in all_pivots if p["type"] == "low" and p["price"] < base_zone["low"]]
                    sl = (max(sl_pivot) if sl_pivot else base_zone["low"]) - 0.5
                    tp = find_nearest_resistance(candles, base_zone["high"], h1_candles)
                else:
                    sl_pivot = [p["price"] for p in all_pivots if p["type"] == "high" and p["price"] > base_zone["high"]]
                    sl = (min(sl_pivot) if sl_pivot else base_zone["high"]) + 0.5
                    tp = find_nearest_support(candles, base_zone["low"], h1_candles)

            md = {
                "entry_zone": {"high": base_zone["high"], "low": base_zone["low"]},
                "sl": float(sl), "tp": float(tp), "danger_zone": float(dz_level),
                "direction": direction, "entry_tf": tf, "detector_name": "Snrc3Detector"
            }
            return [self._create_pattern_fact("SNRC3", 0.85, md)]
        return []
