from typing import Dict, Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    get_base_zone, htf_confirm_solid, find_nearest_support,
    find_nearest_resistance, is_bullish, is_bearish, body_size,
    is_engulfing, sl_buffer
)

class ManipulationDetector(BystraBaseDetector):
    """Manipulation: HTF engulfing -> LTF RBR/DBD entry INSIDE engulfing body.
    Entry must be strictly inside the HTF body, not outside."""
    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        htf_tf = "M15" if tf == "M5" else "H1"
        htf_candles = self._get_candles(context, htf_tf, 5)
        if len(htf_candles) < 3: return []
        
        last, prev = htf_candles[-1], htf_candles[-2]
        eng_type = is_engulfing(prev, last)
        if eng_type not in ("bullish", "bearish"):
            return []
        
        direction = "BUY" if eng_type == "bullish" else "SELL"
        
        # HTF body boundaries
        htf_body_low = min(float(last["open"]), float(last["close"]))
        htf_body_high = max(float(last["open"]), float(last["close"]))
        
        # DZ = beyond HTF engulfing candle opposite edge
        dz_level = htf_body_low if direction == "BUY" else htf_body_high
        
        ltf_candles = self._get_candles(context, tf, 20)
        for i in range(1, len(ltf_candles)-1):
            c = ltf_candles[i]
            c_low, c_high = float(c["low"]), float(c["high"])
            
            if not (htf_body_low <= c_low and c_high <= htf_body_high):
                continue
            
            prev_c = ltf_candles[i-1]
            if direction == "BUY":
                if not (is_bullish(prev_c) and is_bullish(c)):
                    continue
            else:
                if not (is_bearish(prev_c) and is_bearish(c)):
                    continue
            
            base_zone = {"high": c_high, "low": c_low}
            buf = sl_buffer(context)
            sl = htf_body_low - buf if direction == "BUY" else htf_body_high + buf
            tp = find_nearest_resistance(ltf_candles, base_zone["high"]) if direction == "BUY" else find_nearest_support(ltf_candles, base_zone["low"])

            return [self._create_pattern_fact("MANIPULATION", 0.9, {
                "entry_zone": base_zone,
                "sl": float(sl),
                "tp": float(tp),
                "danger_zone": float(dz_level),
                "direction": direction,
                "entry_tf": tf,
                "detector_name": "ManipulationDetector"
            })]
        return []
