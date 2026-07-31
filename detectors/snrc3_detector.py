from typing import Dict, Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    get_base_zone, htf_confirm_solid, find_nearest_support, 
    find_nearest_resistance, find_swing_pivots, check_retest,
    is_bullish, is_bearish, body_size
)

class Snrc3Detector(BystraBaseDetector):
    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        candles = self._get_candles(context, tf, 20)
        if len(candles) < 5: return []
        
        # SNRC3: Strong S/R replaced by engulfing candle battle
        for i in range(1, len(candles) - 2):
            prev, base, brk = candles[i-1], candles[i], candles[i+1]
            
            # Identify engulfing at base
            is_eng = False
            direction = ""
            if is_bullish(brk) and body_size(brk) > body_size(base) and is_bearish(base):
                direction = "BUY"; is_eng = True
            elif is_bearish(brk) and body_size(brk) > body_size(base) and is_bullish(base):
                direction = "SELL"; is_eng = True
            
            if not is_eng: continue
            
            base_zone = get_base_zone(candles, i)
            
            # HTF Confirmation
            htf_tf = "M15" if tf == "M5" else "H1"
            htf_candles = self._get_candles(context, htf_tf, 10)
            h1_candles = self._get_candles(context, "H1", 30)
            
            # Danger Zone check
            if direction == "BUY":
                dz_level = find_nearest_resistance(candles, base_zone["high"], h1_candles)
                if dz_level >= 999999.0: dz_level = base_zone["high"] * 1.05  # fallback 5% above
            else:
                dz_level = find_nearest_support(candles, base_zone["low"], h1_candles)
                if dz_level <= 0: dz_level = base_zone["low"] * 0.95  # fallback 5% below
            
            if not htf_confirm_solid(htf_candles, direction, dz_level):
                continue
            
            # Retest
            if not check_retest(candles, base_zone, direction):
                continue
            
            # Levels
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
                "sl": float(sl),
                "tp": float(tp),
                "danger_zone": float(dz_level),
                "direction": direction,
                "entry_tf": tf,
                "detector_name": "Snrc3Detector"
            }
            return [self._create_pattern_fact("SNRC3", 0.9, md)]
        return []