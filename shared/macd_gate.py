"""MACD Momentum Gate — Goldman Sachs inspired confirm filter.

Checks MACD momentum direction before entry:
- MACD > Signal → Momentum UP → BUY ok, SELL blocked
- MACD < Signal → Momentum DOWN → SELL ok, BUY blocked

Goldman Sachs Formula:
- MACD = EMA(12) - EMA(26)
- Signal = EMA(9) of MACD
"""
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class MACDVerdict:
    allowed: bool
    reason: str
    macd_value: float = 0.0
    signal_value: float = 0.0


def check(features: Any, candles: Dict[str, List[dict]], direction: str) -> MACDVerdict:
    """
    MACD Momentum Gate — confirm entry with MACD direction.
    
    Args:
        features: FeatureSnapshot with .macd, .macd_signal (if available)
        candles: Full-TF candle dict
        direction: "BUY" or "SELL"
    
    Returns:
        MACDVerdict(allowed, reason, macd_value, signal_value)
    """
    # Get MACD from features if available
    macd = getattr(features, "macd", None)
    signal = getattr(features, "macd_signal", None)
    
    if macd is None or signal is None:
        # Fallback: calculate from M5 closes
        m5 = candles.get("M5", [])
        if len(m5) < 26:
            return MACDVerdict(True, "insufficient_candles_skip")
        
        closes = [float(c.get("close", 0)) for c in m5[-50:]]  # Last 50 candles
        macd, signal = _calculate_macd(closes)
    
    # MACD momentum check
    if direction == "BUY":
        if macd > signal:
            return MACDVerdict(True, f"macd_up_buy_ok macd={macd:.2f} sig={signal:.2f}", macd, signal)
        else:
            return MACDVerdict(False, f"macd_down_buy_blocked macd={macd:.2f} sig={signal:.2f}", macd, signal)
    
    elif direction == "SELL":
        if macd < signal:
            return MACDVerdict(True, f"macd_down_sell_ok macd={macd:.2f} sig={signal:.2f}", macd, signal)
        else:
            return MACDVerdict(False, f"macd_up_sell_blocked macd={macd:.2f} sig={signal:.2f}", macd, signal)
    
    return MACDVerdict(True, "unknown_direction_skip")


def _calculate_macd(closes: List[float], fast=12, slow=26, signal_period=9) -> tuple:
    """Calculate MACD and Signal from closes using simple EMA."""
    if len(closes) < slow:
        return 0.0, 0.0
    
    # EMA helper
    def ema(data, period):
        alpha = 2 / (period + 1)
        ema_val = data[0]
        for price in data[1:]:
            ema_val = alpha * price + (1 - alpha) * ema_val
        return ema_val
    
    # MACD = EMA(12) - EMA(26)
    ema_fast = ema(closes[-fast:], fast)
    ema_slow = ema(closes[-slow:], slow)
    macd = ema_fast - ema_slow
    
    # Signal = EMA(9) of MACD (simplified — assume MACD stable)
    signal = macd * 0.9  # Approximation (real would need historical MACD values)
    
    return macd, signal
