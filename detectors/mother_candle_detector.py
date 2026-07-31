from typing import Dict, Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    get_base_zone, htf_confirm_solid, find_nearest_support,
    find_nearest_resistance, find_swing_pivots, check_retest,
    is_bullish, is_bearish, body_size, sl_buffer
)

class MotherCandleDetector(BystraBaseDetector):
    """Mother Candle: 1 candle shadows 4 next candles, breakout B1/B2/B3."""
    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "H1")
        candles = self._get_candles(context, tf, 30)
        if len(candles) < 10: return []
        
        h1_candles = self._get_candles(context, "H1", 30)
        
        for i in range(len(candles) - 8):
            mc = candles[i]
            c1, c2, c3, c4 = candles[i+1], candles[i+2], candles[i+3], candles[i+4]
            b1, b2, b3 = candles[i+5], candles[i+6], candles[i+7]
            
            mc_high, mc_low = float(mc["high"]), float(mc["low"])
            mc_size = mc_high - mc_low
            
            # Size filter XAUUSD 150-500 pips (1.5-5.0 points)
            if not (1.5 <= mc_size <= 5.0): continue
            
            shadow_ok = all(
                mc_low <= float(c["low"]) and float(c["high"]) <= mc_high
                for c in [c1, c2, c3, c4]
            )
            if not shadow_ok: continue
            
            direction = None
            for b in [b1, b2, b3]:
                b_high, b_low = float(b["high"]), float(b["low"])
                if b_high > mc_high + 0.5:
                    direction = "BUY"
                    break
                elif b_low < mc_low - 0.5:
                    direction = "SELL"
                    break
            
            if not direction: continue
            
            buf = sl_buffer(context)
            if direction == "BUY":
                entry = mc_high + 0.5
                sl = mc_low - buf
                tp = entry + mc_size
                dz_level = mc_low  # DZ = below MC low
            else:
                entry = mc_low - 0.5
                sl = mc_high + buf
                tp = entry - mc_size
                dz_level = mc_high  # DZ = above MC high
            
            sr_resist = find_nearest_resistance(candles[:i], mc_high, h1_candles)
            sr_support = find_nearest_support(candles[:i], mc_low, h1_candles)
            mc_close = float(mc["close"])
            if direction == "BUY" and sr_resist and abs(sr_resist - mc_close) < 1.0:
                continue
            if direction == "SELL" and sr_support and abs(sr_support - mc_close) < 1.0:
                continue
            
            return [self._create_pattern_fact("MOTHER_CANDLE", 0.85, {
                "entry_zone": {"high": entry + 0.2, "low": entry - 0.2},
                "sl": float(sl),
                "tp": float(tp),
                "danger_zone": float(dz_level),
                "direction": direction,
                "entry_tf": tf,
                "mc_size": float(mc_size),
                "detector_name": "MotherCandleDetector"
            })]
        return []