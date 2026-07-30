from typing import Dict, Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    get_base_zone, htf_confirm_solid, find_nearest_support, 
    find_nearest_resistance, find_swing_pivots, check_retest,
    is_bullish, is_bearish
)

class Hybrid1Detector(BystraBaseDetector):
    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        candles = self._get_candles(context, tf, 20)
        if len(candles) < 5: return []
        
        # HYBRID1: Reversal at RBR/DBD/QMR retest.
        for i in range(1, len(candles) - 2):
            prev, base, brk = candles[i-1], candles[i], candles[i+1]
            
            direction = ""
            if is_bullish(prev) and is_bullish(brk): direction = "BUY"
            elif is_bearish(prev) and is_bearish(brk): direction = "SELL"
            
            if not direction: continue
            
            base_zone = get_base_zone(candles, i)
            
            # DZ check: HTF candle body must NOT touch DZ
            htf_tf = "M15" if tf == "M5" else "H1"
            htf_candles = self._get_candles(context, htf_tf, 10)
            dz_level = find_nearest_resistance(candles, base_zone["high"]) if direction == "BUY" else find_nearest_support(candles, base_zone["low"])
            
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
                "detector_name": "Hybrid1Detector"
            }
            return [self._create_pattern_fact("HYBRID1", 0.85, md)]
        return []

class Hybrid2Detector(BystraBaseDetector):
    def detect(self, context: Any) -> List[Any]:
        # Hybrid1 + 2 parallel trendlines. Entry=3rd trendline touch.
        # ponytail: trendline detection skipped, using Hybrid1 logic as proxy
        return Hybrid1Detector().detect(context)
