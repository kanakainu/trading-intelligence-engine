from typing import Dict, Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    get_base_zone, htf_confirm_solid, find_nearest_support, 
    find_nearest_resistance, is_bullish, is_bearish, body_size
)

class ManipulationDetector(BystraBaseDetector):
    """Manipulation: HTF engulfing -> LTF RBR/DBD inside body."""
    def detect(self, context: Any) -> List[Any]:
        # Valid manipulation appears on HTF
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        htf_tf = "M15" if tf == "M5" else "H1"
        htf_candles = self._get_candles(context, htf_tf, 5)
        if len(htf_candles) < 2: return []
        
        curr_htf, prev_htf = htf_candles[-1], htf_candles[-2]
        direction = ""
        if is_bullish(curr_htf) and body_size(curr_htf) > body_size(prev_htf):
            direction = "BUY"
        elif is_bearish(curr_htf) and body_size(curr_htf) > body_size(prev_htf):
            direction = "SELL"
        
        if not direction: return []
        
        # LTF must have RBR/DBD inside HTF body
        ltf_candles = self._get_candles(context, tf, 20)
        htf_body_low = min(float(curr_htf["open"]), float(curr_htf["close"]))
        htf_body_high = max(float(curr_htf["open"]), float(curr_htf["close"]))
        
        for i in range(1, len(ltf_candles)-1):
            c = ltf_candles[i]
            if htf_body_low <= float(c["low"]) and float(c["high"]) <= htf_body_high:
                # Potential entry point inside body
                base_zone = {"high": float(c["high"]), "low": float(c["low"])}
                sl = htf_body_low - 0.5 if direction == "BUY" else htf_body_high + 0.5
                tp = find_nearest_resistance(ltf_candles, base_zone["high"]) if direction == "BUY" else find_nearest_support(ltf_candles, base_zone["low"])
                
                return [self._create_pattern_fact("MANIPULATION", 0.9, {
                    "entry_zone": base_zone,
                    "sl": float(sl),
                    "tp": float(tp),
                    "direction": direction,
                    "entry_tf": tf,
                    "detector_name": "ManipulationDetector"
                })]
        return []
