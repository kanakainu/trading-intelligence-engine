from typing import Dict, Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    get_base_zone, htf_confirm_solid, check_retest,
    is_bullish, is_bearish, body_size, sl_buffer
)

class Snrc1Detector(BystraBaseDetector):
    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        candles = self._get_candles(context, tf, 20)
        if len(candles) < 5: return []

        # Get precomputed features (B3.5 migration)
        features = self._get_features(context)

        # RBR (BUY) or DBD (SELL) + Base at S/R
        for i in range(1, len(candles) - 2):
            prev, base, brk = candles[i-1], candles[i], candles[i+1]

            # 1. Pattern Detection
            direction = ""
            if is_bullish(prev) and is_bullish(brk) and body_size(brk) > body_size(base):
                direction = "BUY"  # RBR
            elif is_bearish(prev) and is_bearish(brk) and body_size(brk) > body_size(base):
                direction = "SELL"  # DBD
            if not direction: continue

            # 2. Base at structural S/R
            base_zone = get_base_zone(candles, i)

            # Use precomputed pivots from FeatureSnapshot if available
            if features:
                # Check if base_zone overlaps with nearest S/R levels from features
                h1_sup = features.get_nearest_support("H1") or 0.0
                h1_res = features.get_nearest_resistance("H1") or 999999.0
                at_sr = (base_zone["low"] <= h1_res <= base_zone["high"]) or \
                        (base_zone["low"] <= h1_sup <= base_zone["high"])
            else:
                # Fallback: legacy pivot check from candles
                from detectors.common import find_swing_pivots
                pivots = find_swing_pivots(candles[:i+1])
                at_sr = any(base_zone["low"] <= p["price"] <= base_zone["high"] for p in pivots)
            if not at_sr: continue

            # 3. HTF Confirmation
            htf_tf = "M15" if tf == "M5" else "H1"
            htf_candles = self._get_candles(context, htf_tf, 10)
            h1_candles = self._get_candles(context, "H1", 30)

            # Danger Zone — use precomputed S/R if available
            if features:
                if direction == "BUY":
                    dz_level = features.get_nearest_resistance("H1") or base_zone["high"] * 1.05
                else:
                    dz_level = features.get_nearest_support("H1") or base_zone["low"] * 0.95
            else:
                from detectors.common import find_nearest_support, find_nearest_resistance
                if direction == "BUY":
                    dz_level = find_nearest_resistance(candles, base_zone["high"], h1_candles)
                    if dz_level >= 999999.0: dz_level = base_zone["high"] * 1.05
                else:
                    dz_level = find_nearest_support(candles, base_zone["low"], h1_candles)
                    if dz_level <= 0: dz_level = base_zone["low"] * 0.95

            if not htf_confirm_solid(htf_candles, direction, dz_level):
                continue

            # Retest
            if not check_retest(candles, base_zone, direction):
                continue

            # SL/TP — use precomputed S/R if available
            if features:
                if direction == "BUY":
                    sl = base_zone["low"] - 0.5
                    tp = features.get_nearest_resistance("H1") or base_zone["high"] * 1.02
                else:
                    sl = base_zone["high"] + 0.5
                    tp = features.get_nearest_support("H1") or base_zone["low"] * 0.98
            else:
                from detectors.common import find_swing_pivots, find_nearest_support, find_nearest_resistance
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
                "detector_name": "Snrc1Detector"
            }
            return [self._create_pattern_fact("SNRC1", 0.9, md)]
        return []
