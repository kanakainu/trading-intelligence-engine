"""MicrostructureEngine — fused score: trend alignment + compression + pullback."""
from typing import List, Dict

def _body(c): return abs(float(c["close"]) - float(c["open"]))
def _rng(c): r = float(c["high"]) - float(c["low"]); return r if r > 0 else 1e-9

def _trend_score(candles: List[Dict]) -> float:
    """Consecutive closes in same direction → higher score."""
    if len(candles) < 3: return 50.0
    closes = [float(c["close"]) for c in candles[-5:]]
    ups = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
    return (ups / (len(closes)-1)) * 100

def _compression_score(candles: List[Dict], atr: float = 0.0) -> float:
    """Low ATR relative to recent average → compression forming → higher score."""
    if len(candles) < 5: return 50.0
    ranges = [_rng(c) for c in candles[-5:]]
    avg = sum(ranges) / len(ranges)
    last = ranges[-1]
    # Smaller last range vs avg = higher compression score
    ratio = (avg - last) / avg if avg > 0 else 0
    return min(100.0, max(0.0, ratio * 100 + 50))

def _pullback_score(candles: List[Dict]) -> float:
    """Shallow pullback after impulse → higher score."""
    if len(candles) < 3: return 50.0
    bodies = [_body(c) / _rng(c) for c in candles[-3:]]
    return min(100.0, (sum(bodies) / len(bodies)) * 100)

def calculate_score(candles_m5: List[Dict], atr: float = 0.0) -> float:
    t = _trend_score(candles_m5)
    c = _compression_score(candles_m5, atr)
    p = _pullback_score(candles_m5)
    return round(t * 0.4 + c * 0.3 + p * 0.3, 2)
