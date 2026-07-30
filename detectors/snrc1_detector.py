from typing import Dict, Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    get_base_zone, htf_confirm_solid, find_nearest_support, 
    find_nearest_resistance, find_swing_pivots, check_retest,
    is_bullish, is_bearish, body_size
)

class Snrc1Detector(BystraBaseDetector):
    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        candles = self._get_candles(context, tf, 20)
        if len(candles) < 5: return []
        
        # RBR (BUY) or DBD (SELL) + Base at S/R
        for i in range(1, len(candles) - 2):
            prev, base, brk = candles[i-1], candles[i], candles[i+1]
            
            # 1. Pattern Detection
            direction = ""
            if is_bullish(prev) and is_bullish(brk) and body_size(brk) > body_size(base):
                direction = "BUY" # RBR
            elif is_bearish(prev) and is_bearish(brk) and body_size(brk) > body_size(base):
                direction = "SELL" # DBD
            if not direction: continue
            
            # 2. Base at structural S/R
            base_zone = get_base_zone(candles, i)
            pivots = find_swing_pivots(candles[:i+1])
            at_sr = any(base_zone["low"] <= p["price"] <= base_zone["high"] for p in pivots)
            if not at_sr: continue

            # 3. HTF Confirmation
            htf_tf = "M15" if tf == "M5" else "H1"
            htf_candles = self._get_candles(context, htf_tf, 10)
            dz_level = find_nearest_resistance(candles, base_zone["high"]) if direction == "BUY" else find_nearest_support(candles, base_zone["low"])
            if not htf_confirm_solid(htf_candles, direction, dz_level):
                continue

            # 4. Trigger = Retest after breakout
            if not check_retest(candles, base_zone, direction):
                continue

            # 5. SL = last swing low/high OUTSIDE base zone + 0.5 buffer
            all_pivots = find_swing_pivots(candles)
            if direction == "BUY":
                sl_pivot = [p["price"] for p in all_pivots if p["type"] == "low" and p["price"] < base_zone["low"]]
                sl = (max(sl_pivot) if sl_pivot else base_zone["low"]) - 0.5
                tp = find_nearest_resistance(candles, base_zone["high"])
            else:
                sl_pivot = [p["price"] for p in all_pivots if p["type"] == "high" and p["price"] > base_zone["high"]]
                sl = (min(sl_pivot) if sl_pivot else base_zone["high"]) + 0.5
                tp = find_nearest_support(candles, base_zone["low"])

            md = {
                "entry_zone": {"high": base_zone["high"], "low": base_zone["low"]},
                "sl": float(sl),
                "tp": float(tp),
                "danger_zone": float(dz_level),
                "direction": direction,
                "entry_tf": tf,
                "detector_name": "Snrc1Detector"
            }
            return [self._create_pattern_fact("SNRC1", 0.9, md)]
        return []
