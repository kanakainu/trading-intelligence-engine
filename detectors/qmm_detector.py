from typing import Dict, Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    get_base_zone, htf_confirm_solid, find_nearest_support, 
    find_nearest_resistance, find_swing_pivots, check_retest,
    is_bullish, is_bearish
)

class QmmDetector(BystraBaseDetector):
    """QMM: Failed QMR -> entry at left shoulder of failed QMR."""
    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        candles = self._get_candles(context, tf, 40)
        if len(candles) < 15: return []
        
        pivots = find_swing_pivots(candles)
        if len(pivots) < 5: return []
        
        # Detect Failed QMR (price breaks past head)
        for i in range(4, len(pivots)):
            p4, p3, p2, p1, p0 = pivots[i-4], pivots[i-3], pivots[i-2], pivots[i-1], pivots[i]
            
            # Left shoulder level
            ls_level = p4["price"]
            
            # Failed QMR BUY (Left shoulder was for BUY, but head p2 broken downwards)
            if p4["type"]=="low" and p3["type"]=="high" and p2["type"]=="low" and p0["price"] < p2["price"]:
                direction = "SELL" # Reverse entry at LS
                base_zone = {"high": ls_level + 0.2, "low": ls_level - 0.2}
                
                # SL above local high, TP next support
                sl = p3["price"] + 0.5
                tp = find_nearest_support(candles, ls_level)
                
                # Confirmation
                htf_tf = "M15" if tf == "M5" else "H1"
                if htf_confirm_solid(self._get_candles(context, htf_tf, 10), direction, tp):
                    return [self._create_pattern_fact("QMM", 0.75, {
                        "entry_zone": base_zone,
                        "sl": float(sl),
                        "tp": float(tp),
                        "direction": direction,
                        "entry_tf": tf,
                        "detector_name": "QmmDetector"
                    })]
        return []
