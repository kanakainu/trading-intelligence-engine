"""HMMRegimeDetector — simple state machine using ATR ratio + trend analysis.
Not a real HMM; class name reflects the conceptual interface.
"""
from typing import List, Dict


class HMMRegimeDetector:
    """Detect market regime from H1 candles using ATR/range ratio + trend slope."""

    def detect(self, candles: List[Dict]) -> str:
        """Return regime: TRENDING_BULL, TRENDING_BEAR, SIDEWAYS, VOLATILE."""
        if len(candles) < 14:
            return "SIDEWAYS"

        highs = [float(c["high"]) for c in candles[-14:]]
        lows = [float(c["low"]) for c in candles[-14:]]
        closes = [float(c["close"]) for c in candles[-14:]]

        # ATR (14-period)
        trs = []
        for i in range(1, len(candles[-14:])):
            h = float(candles[-14:][i]["high"])
            l = float(candles[-14:][i]["low"])
            pc = float(candles[-14:][i - 1]["close"])
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        atr = sum(trs) / len(trs) if trs else 0.0

        # H1 range (high - low over window)
        h1_range = max(highs) - min(lows)
        ratio = atr / h1_range if h1_range > 0 else 0

        # VOLATILE check
        if ratio > 0.8:
            return "VOLATILE"

        # Trend slope via linear regression on closes
        n = len(closes)
        x_avg = (n - 1) / 2.0
        y_avg = sum(closes) / n
        num = sum((i - x_avg) * (c - y_avg) for i, c in enumerate(closes))
        den = sum((i - x_avg) ** 2 for i in range(n))
        slope = num / den if den != 0 else 0.0

        atr_pct = atr / y_avg if y_avg else 0
        slope_pct = slope / y_avg if y_avg else 0

        # Strong trend
        if abs(slope_pct) > 0.0002 and atr_pct < 0.005:
            return "TRENDING_BULL" if slope > 0 else "TRENDING_BEAR"

        return "SIDEWAYS"
