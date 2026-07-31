from typing import Dict, Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    get_base_zone, htf_confirm_solid, is_strong_sr_broken, sl_buffer,
    is_bullish, is_bearish
)

class Snrc2Detector(BystraBaseDetector):
    """SNRC2: RBD/DBR at Strong S/R. MUST break previous Strong Support/Resistance."""
    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        candles = self._get_candles(context, tf, 20)
        if len(candles) < 5: return []

        features = self._get_features(context)

        for i in range(1, len(candles) - 2):
            prev, base, brk = candles[i-1], candles[i], candles[i+1]

            direction = ""
            if is_bullish(prev) and is_bearish(brk): direction = "SELL"  # RBD
            elif is_bearish(prev) and is_bullish(brk): direction = "BUY"  # DBR
            if not direction: continue

            base_zone = get_base_zone(candles, i)
            brk_close = float(brk["close"])

            # HTF S/R check using features if available
            htf_tf = "M15" if tf == "M5" else "H1"
            htf_candles = self._get_candles(context, htf_tf, 10)
            h1_candles = self._get_candles(context, "H1", 30)

            if features:
                h1_sup = features.get_nearest_support("H1") or 0.0
                h1_res = features.get_nearest_resistance("H1") or 999999.0
                # Strong S/R broken check
                sr_broken = (direction == "BUY" and brk_close > h1_res) or \
                            (direction == "SELL" and brk_close < h1_sup)
                if not sr_broken: continue
                dz_level = h1_res if direction == "BUY" else h1_sup
                if dz_level <= 0 or dz_level >= 999999.0:
                    dz_level = base_zone["high"] * 1.05 if direction == "BUY" else base_zone["low"] * 0.95
            else:
                if not is_strong_sr_broken(context, direction, brk_close): continue
                from detectors.common import find_nearest_support, find_nearest_resistance
                if direction == "BUY":
                    dz_level = find_nearest_resistance(candles, base_zone["high"], h1_candles)
                    if dz_level >= 999999.0: dz_level = base_zone["high"] * 1.05
                else:
                    dz_level = find_nearest_support(candles, base_zone["low"], h1_candles)
                    if dz_level <= 0: dz_level = base_zone["low"] * 0.95

            if not htf_confirm_solid(htf_candles, direction, dz_level): continue

            # SL/TP
            if features:
                sl = base_zone["low"] - 0.5 if direction == "BUY" else base_zone["high"] + 0.5
                tp = features.get_nearest_resistance("H1") or base_zone["high"] * 1.02 if direction == "BUY" else \
                     features.get_nearest_support("H1") or base_zone["low"] * 0.98
            else:
                from detectors.common import find_nearest_support, find_nearest_resistance
                sl = base_zone["low"] - 0.5 if direction == "BUY" else base_zone["high"] + 0.5
                tp = find_nearest_resistance(candles, base_zone["high"], h1_candles) if direction == "BUY" else \
                     find_nearest_support(candles, base_zone["low"], h1_candles)

            md = {
                "entry_zone": {"high": base_zone["high"], "low": base_zone["low"]},
                "sl": float(sl), "tp": float(tp), "danger_zone": float(dz_level),
                "direction": direction, "entry_tf": tf, "detector_name": "Snrc2Detector"
            }
            return [self._create_pattern_fact("SNRC2", 0.85, md)]
        return []
