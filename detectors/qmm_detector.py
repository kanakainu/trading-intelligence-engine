from typing import Dict, Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    get_base_zone, htf_confirm_solid, find_nearest_support,
    find_nearest_resistance, find_swing_pivots, check_retest,
    is_bullish, is_bearish, is_engulfing, sl_buffer
)

class QmmDetector(BystraBaseDetector):
    """QMM: Failed QMR -> entry at left shoulder of failed QMR.
    Left shoulder level = entry zone. Entry point must be IN LINE with LS."""
    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        candles = self._get_candles(context, tf, 40)
        if len(candles) < 15: return []
        
        pivots = find_swing_pivots(candles)
        if len(pivots) < 5: return []
        
        h1_candles = self._get_candles(context, "H1", 30)
        
        for i in range(4, len(pivots)):
            p4, p3, p2, p1, p0 = pivots[i-4], pivots[i-3], pivots[i-2], pivots[i-1], pivots[i]
            
            ls_level = p4["price"]
            head_level = p2["price"]
            
            # Detect failed QMR
            if p4["type"] == "low" and p3["type"] == "high" and p2["type"] == "low" and p0["price"] < p2["price"]:
                direction = "SELL"
                entry_zone = {"high": ls_level + 0.3, "low": ls_level - 0.3}
                
                recent_price = float(candles[-1]["close"])
                if not (entry_zone["low"] <= recent_price <= entry_zone["high"]):
                    continue
                
                buf = sl_buffer(context)
                sl = p3["price"] + buf
                tp = find_nearest_support(candles, ls_level, h1_candles)
                dz_level = p2["price"]  # DZ = beyond head
                
                htf_tf = "M15" if tf == "M5" else "H1"
                htf_candles = self._get_candles(context, htf_tf, 10)
                if not htf_confirm_solid(htf_candles, direction, dz_level):
                    continue
                    
                return [self._create_pattern_fact("QMM", 0.75, {
                    "entry_zone": entry_zone,
                    "sl": float(sl),
                    "tp": float(tp),
                    "danger_zone": float(dz_level),
                    "direction": direction,
                    "entry_tf": tf,
                    "detector_name": "QmmDetector"
                })]
                
            elif p4["type"] == "high" and p3["type"] == "low" and p2["type"] == "high" and p0["price"] > p2["price"]:
                direction = "BUY"
                entry_zone = {"high": ls_level + 0.3, "low": ls_level - 0.3}
                
                recent_price = float(candles[-1]["close"])
                if not (entry_zone["low"] <= recent_price <= entry_zone["high"]):
                    continue
                    
                buf = sl_buffer(context)
                sl = p3["price"] - buf
                tp = find_nearest_resistance(candles, ls_level, h1_candles)
                dz_level = p2["price"]
                
                htf_tf = "M15" if tf == "M5" else "H1"
                htf_candles = self._get_candles(context, htf_tf, 10)
                if not htf_confirm_solid(htf_candles, direction, dz_level):
                    continue
                    
                return [self._create_pattern_fact("QMM", 0.75, {
                    "entry_zone": entry_zone,
                    "sl": float(sl),
                    "tp": float(tp),
                    "danger_zone": float(dz_level),
                    "direction": direction,
                    "entry_tf": tf,
                    "detector_name": "QmmDetector"
                })]
        return []