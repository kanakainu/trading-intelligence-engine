from typing import Dict, Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    get_base_zone, htf_confirm_solid, find_nearest_support,
    find_nearest_resistance, find_swing_pivots, check_retest,
    is_bullish, is_bearish, sl_buffer
)

class QmrDetector(BystraBaseDetector):
    """QMR: HH->LL->HH->LL(higher)->HH for BUY right shoulder."""
    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        candles = self._get_candles(context, tf, 40)
        if len(candles) < 15: return []
        
        pivots = find_swing_pivots(candles)
        if len(pivots) < 4: return []
        
        h1_candles = self._get_candles(context, "H1", 30)
        
        for i in range(4, len(pivots)):
            p4, p3, p2, p1, p0 = pivots[i-4], pivots[i-3], pivots[i-2], pivots[i-1], pivots[i]
            
            direction = ""
            entry_level = 0.0
            
            if p4["type"]=="low" and p3["type"]=="high" and p2["type"]=="low" and p1["type"]=="high" and p2["price"] < p4["price"] and p1["price"] > p3["price"]:
                direction = "BUY"
                entry_level = p4["price"]
            
            elif p4["type"]=="high" and p3["type"]=="low" and p2["type"]=="high" and p1["type"]=="low" and p2["price"] > p4["price"] and p1["price"] < p3["price"]:
                direction = "SELL"
                entry_level = p4["price"]

            if not direction: continue
            
            base_zone = {"high": entry_level + 0.2, "low": entry_level - 0.2}
            
            htf_tf = "M15" if tf == "M5" else "H1"
            htf_candles = self._get_candles(context, htf_tf, 10)
            # DZ = beyond head of the M/W pattern
            dz_level = p2["price"]
            
            if not htf_confirm_solid(htf_candles, direction, dz_level):
                continue
                
            if not check_retest(candles, base_zone, direction):
                continue

            buf = sl_buffer(context)
            sl = p2["price"] + buf if direction == "SELL" else p2["price"] - buf
            tp = find_nearest_resistance(candles, entry_level, h1_candles) if direction == "BUY" else find_nearest_support(candles, entry_level, h1_candles)

            return [self._create_pattern_fact("QMR", 0.8, {
                "entry_zone": base_zone,
                "sl": float(sl),
                "tp": float(tp),
                "danger_zone": float(dz_level),
                "direction": direction,
                "entry_tf": tf,
                "detector_name": "QmrDetector"
            })]
        return []