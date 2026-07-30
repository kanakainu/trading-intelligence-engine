from typing import Dict, Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    get_base_zone, htf_confirm_solid, find_nearest_support, 
    find_nearest_resistance, find_swing_pivots, check_retest,
    is_bullish, is_bearish, body_size
)

class Hybrid2Detector(BystraBaseDetector):
    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        candles = self._get_candles(context, tf, 25)
        if len(candles) < 10: return []
        
        # Hybrid 2: Hybrid 1 + 2 parallel trendlines. Entry at 3rd trendline.
        for i in range(2, len(candles) - 3):
            base_zone = get_base_zone(candles, i)
            
            # Hybrid 1 reversal pattern detection (retest at RBR/DBD/QMR level)
            # For simplicity, we use base zone retest as core Hybrid 1 logic
            direction = "BUY" if is_bullish(candles[i+1]) else "SELL"
            
            # Trendline check (confluence)
            tl_bull = context.metadata.get("trendline_bullish", False)
            tl_bear = context.metadata.get("trendline_bearish", False)
            if direction == "BUY" and not tl_bull: continue
            if direction == "SELL" and not tl_bear: continue
            
            # HTF Confirmation
            htf_tf = "M15" if tf == "M5" else "H1"
            htf_candles = self._get_candles(context, htf_tf, 10)
            dz_level = find_nearest_resistance(candles, base_zone["high"]) if direction == "BUY" else find_nearest_support(candles, base_zone["low"])
            
            if not htf_confirm_solid(htf_candles, direction, dz_level):
                continue
                
            # Retest check
            if not check_retest(candles, base_zone, direction):
                continue

            # SL/TP Structural
            all_pivots = find_swing_pivots(candles)
            if direction == "BUY":
                sl_p = [p["price"] for p in all_pivots if p["type"] == "low" and p["price"] < base_zone["low"]]
                sl = (max(sl_p) if sl_p else base_zone["low"]) - 0.5
                tp = find_nearest_resistance(candles, base_zone["high"])
            else:
                sl_p = [p["price"] for p in all_pivots if p["type"] == "high" and p["price"] > base_zone["high"]]
                sl = (min(sl_p) if sl_p else base_zone["high"]) + 0.5
                tp = find_nearest_support(candles, base_zone["low"])

            return [self._create_pattern_fact("HYBRID2", 0.85, {
                "entry_zone": base_zone,
                "sl": float(sl),
                "tp": float(tp),
                "danger_zone": float(dz_level),
                "direction": direction,
                "entry_tf": tf,
                "detector_name": "Hybrid2Detector"
            })]
        return []
