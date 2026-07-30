from typing import Dict, Any, List
from detectors.base_detector import BystraBaseDetector
from detectors.common import (
    get_base_zone, find_nearest_support, find_nearest_resistance,
    find_swing_pivots, is_bullish, is_bearish, body_size, is_engulfing
)


class ClabDetector(BystraBaseDetector):
    """CLAB: Confirmation Like a Boss.
    NOT a setup. CONFIRMATION METHOD — involve Engulfing + Confluence.
    Returns PASS/FAIL gate entry, NOT buy/sell signal.
    """

    def detect(self, context: Any) -> List[Any]:
        tf = getattr(context, "timeframe", None) or context.metadata.get("timeframe", "M5")
        candles = self._get_candles(context, tf, 30)
        if len(candles) < 10: return []

        # 1. Strong Engulfing Pattern — check last 3 candles
        curr, prev = candles[-1], candles[-2]
        engulfing = is_engulfing(prev, curr)
        if not engulfing: return []

        direction = "BUY" if engulfing == "bullish" else "SELL"

        # 2. Confluence Check
        confluence = []
        pivots = find_swing_pivots(candles)
        curr_close = float(curr.get("close"))

        # 2a. Near strong support/resistance?
        if direction == "BUY":
            near_support = any(abs(curr_close - p["price"]) / p["price"] < 0.003 
                             for p in pivots if p["type"] == "low" and p["price"] < curr_close)
            if near_support: confluence.append("near_support")
        else:
            near_resistance = any(abs(curr_close - p["price"]) / p["price"] < 0.003 
                                for p in pivots if p["type"] == "high" and p["price"] > curr_close)
            if near_resistance: confluence.append("near_resistance")

        # 2b. Trendline align?
        tl_bull = context.metadata.get("trendline_bullish", False)
        tl_bear = context.metadata.get("trendline_bearish", False)
        if (direction == "BUY" and tl_bull) or (direction == "SELL" and tl_bear):
            confluence.append("trendline_align")

        # 2c. HTF bias alignment?
        htf_tf = "M15" if tf == "M5" else "H1"
        htf_candles = self._get_candles(context, htf_tf, 10)
        if len(htf_candles) >= 3:
            htf_last = htf_candles[-1]
            if (direction == "BUY" and is_bullish(htf_last)) or (direction == "SELL" and is_bearish(htf_last)):
                confluence.append("htf_bias")

        # 3. Gate decision: at least 2 confluences needed for CLAB PASS
        gate_pass = len(confluence) >= 2

        # Return CLAB confirmation fact
        return [self._create_pattern_fact("CLAB", 0.9 if gate_pass else 0.5, {
            "gate_pass": gate_pass,
            "direction": direction,
            "confluence_count": len(confluence),
            "confluences": confluence,
            "entry_tf": tf,
            "detector_name": "ClabDetector"
        })]
