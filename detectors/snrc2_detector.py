from typing import Dict, Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    get_base_zone, htf_confirm_solid, find_nearest_support,
    find_nearest_resistance, find_swing_pivots, check_retest,
    is_bullish, is_bearish, is_strong_sr_broken, sl_buffer
)

class Snrc2Detector(BystraBaseDetector):
    """SNRC2: RBD/DBR at Strong S/R. MUST break previous Strong Support/Resistance."""
    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        candles = self._get_candles(context, tf, 20)
        if len(candles) < 5: return []
        
        for i in range(1, len(candles) - 2):
            prev, base, brk = candles[i-1], candles[i], candles[i+1]
            
            direction = ""
            if is_bullish(prev) and is_bearish(brk): direction = "SELL"  # RBD
            elif is_bearish(prev) and is_bullish(brk): direction = "BUY"  # DBR
            if not direction: continue
            
            base_zone = get_base_zone(candles, i)
            brk_close = float(brk["close"])
            
            # HTF S/R levels for "Strong" check
            htf_tf = "M15" if tf == "M5" else "H1"
            htf_candles = self._get_candles(context, htf_tf, 10)
            htf_pivots = find_swing_pivots(htf_candles)
            
            strong_break = False
            if direction == "BUY":
                htf_res = [p["price"] for p in htf_pivots if p["type"] == "high"]
                if htf_res and brk_close > min(htf_res):
                    strong_break = True
            else:
                htf_sup = [p["price"] for p in htf_pivots if p["type"] == "low"]
                if htf_sup and brk_close < max(htf_sup):
                    strong_break = True
            
            if not strong_break: continue
            
            # Danger Zone check
            h1_candles = self._get_candles(context, "H1", 30)
            if direction == "BUY":
                dz_level = find_nearest_resistance(candles, base_zone["high"], h1_candles)
                if dz_level >= 999999.0: dz_level = base_zone["high"] * 1.05
            else:
                dz_level = find_nearest_support(candles, base_zone["low"], h1_candles)
                if dz_level <= 0: dz_level = base_zone["low"] * 0.95
            
            # HTF Confirmation
            htf_candles = self._get_candles(context, htf_tf, 10)
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
                "detector_name": "Snrc2Detector"
            }
            return [self._create_pattern_fact("SNRC2", 0.9, md)]
        return []