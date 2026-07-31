from typing import Dict, Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    get_base_zone, htf_confirm_solid, find_nearest_support,
    find_nearest_resistance, find_swing_pivots, check_retest,
    is_bullish, is_bearish, body_size, sl_buffer
)

class BlindspotDetector(BystraBaseDetector):
    """Blindspot: Failed Engulfing + Significant Break (Swap)."""
    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        candles = self._get_candles(context, tf, 30)
        if len(candles) < 10: return []
        
        h1_candles = self._get_candles(context, "H1", 30)
        
        for i in range(1, len(candles) - 2):
            prev, curr, next_c = candles[i-1], candles[i], candles[i+1]
            
            # Failed Engulfing (e.g. Bullish Engulfing broken downwards)
            if is_bullish(curr) and body_size(curr) > body_size(prev):
                if float(next_c["close"]) < float(curr["low"]):
                    direction = "SELL"
                    base_zone = get_base_zone(candles, i-1)
                    
                    buf = sl_buffer(context)
                    all_pivots = find_swing_pivots(candles, n=2)
                    highs = [p["price"] for p in all_pivots if p["type"] == "high" and p["price"] > float(base_zone["high"])]
                    sl = (min(highs) if highs else float(base_zone["high"])) + buf
                    tp = find_nearest_support(candles, float(base_zone["low"]), h1_candles)
                    dz_level = float(curr["high"])  # DZ = above engulfing high
                    
                    htf_tf = "M15" if tf == "M5" else "H1"
                    if htf_confirm_solid(self._get_candles(context, htf_tf, 10), direction, dz_level):
                        return [self._create_pattern_fact("BLINDSPOT", 0.75, {
                            "entry_zone": base_zone,
                            "sl": float(sl),
                            "tp": float(tp),
                            "danger_zone": float(dz_level),
                            "direction": direction,
                            "entry_tf": tf,
                            "detector_name": "BlindspotDetector"
                        })]
        return []