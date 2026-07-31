from typing import Dict, Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    get_base_zone, htf_confirm_solid, check_retest,
    is_bullish, is_bearish, body_size, is_engulfing, sl_buffer,
)


class Blindspot2Detector(BystraBaseDetector):
    """Blindspot 2: Blindspot 1 + trendline confluence.
    Sama dengan blindspot 1, tapi ditambah trendline sebagai confluence atau confirmation.
    Entry lebih yakin dengan trendline yang align.
    """

    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        candles = self._get_candles(context, tf, 50)
        if len(candles) < 10: return []

        trendline_bullish = context.metadata.get("trendline_bullish", False)
        trendline_bearish = context.metadata.get("trendline_bearish", False)

        for i in range(5, len(candles)):
            curr = candles[i]
            prev_2 = candles[i-2]
            
            # Blindspot 1 logic (strong candle + small retrace)
            # Strong candle body
            body_ratio = body_size(curr) / (float(curr.get("high")) - float(curr.get("low"))) if (float(curr.get("high")) - float(curr.get("low"))) > 0 else 0
            if body_ratio < 0.7: continue # Not a strong candle

            direction = ""
            if is_bullish(curr) and is_bearish(prev_2) and body_size(prev_2) < body_size(curr) * 0.5:
                direction = "BUY"
            elif is_bearish(curr) and is_bullish(prev_2) and body_size(prev_2) < body_size(curr) * 0.5:
                direction = "SELL"

            if not direction: continue

            # Blindspot 2 specific: Trendline confluence
            if direction == "BUY" and not trendline_bullish: continue
            if direction == "SELL" and not trendline_bearish: continue

            # Get base zone for SL/TP reference
            base_zone = get_base_zone(candles, i-1) # Base is previous candle

            # HTF Confirmation mandatory (M15 or H1)
            htf_tf = "M15" if tf == "M5" else "H1"
            htf_candles = self._get_candles(context, htf_tf, 10)
            features = self._get_features(context)
            c_high, c_low = float(curr.get("high")), float(curr.get("low"))
            if features:
                dz_level = features.get_nearest_resistance("H1") if direction == "BUY" else features.get_nearest_support("H1")
                dz_level = dz_level or (c_high * 1.02 if direction == "BUY" else c_low * 0.98)
            else:
                from detectors.common import find_nearest_support, find_nearest_resistance
                dz_level = find_nearest_resistance(candles, c_high) if direction == "BUY" else find_nearest_support(candles, c_low)

            if not htf_confirm_solid(htf_candles, direction, dz_level):
                continue

            # Retest check (price return to base zone after breakout)
            if not check_retest(candles, base_zone, direction): continue

            # SL = beyond base zone + buffer
            all_pivots = self._get_pivots(candles, n=2)
            buf = sl_buffer(context)
            if direction == "BUY":
                lows = [p["price"] for p in all_pivots if p["type"] == "low" and p["price"] < float(base_zone["low"])]
                sl = (max(lows) if lows else float(base_zone["low"])) - buf
            else:
                highs = [p["price"] for p in all_pivots if p["type"] == "high" and p["price"] > float(base_zone["high"])]
                sl = (min(highs) if highs else float(base_zone["high"])) + buf
            # TP = beyond current move (e.g. 2x ATR or next S/R)
            if features:
                tp = features.get_nearest_resistance("H1") if direction == "BUY" else features.get_nearest_support("H1")
                tp = tp or (c_high * 1.02 if direction == "BUY" else c_low * 0.98)
            else:
                from detectors.common import find_nearest_support, find_nearest_resistance
                tp = find_nearest_resistance(candles, c_high) if direction == "BUY" else find_nearest_support(candles, c_low)

            return [self._create_pattern_fact("BLINDSPOT2", 0.9, {
                "entry_zone": base_zone,
                "sl": float(sl),
                "tp": float(tp),
                "danger_zone": float(dz_level),
                "direction": direction,
                "entry_tf": tf,
                "detector_name": "Blindspot2Detector"
            })]

        return []
