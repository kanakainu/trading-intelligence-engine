"""TickVelocityEngine — price acceleration scoring."""
from typing import List, Dict

def _h(c, k): return float(c.get(k) or c.get(k.capitalize()) or 0)
def _body(c): return abs(_h(c, "close") - _h(c, "open"))
def _range(c): return _h(c, "high") - _h(c, "low")

def calculate_score(candles_m1: List[Dict]) -> float:
    """Calculate tick velocity 0-100. Higher = faster price action."""
    if len(candles_m1) < 5: return 50.0
    
    # Body ratio = body / range (conviction)
    ratios = []
    for c in candles_m1[-5:]:
        rng = _range(c)
        if rng > 0:
            ratios.append(_body(c) / rng)
        else:
            ratios.append(0)
    
    avg_ratio = sum(ratios) / len(ratios) if ratios else 0.0
    
    # Score: 0.0-0.3 = low (20-50), 0.3-0.7 = normal (50-80), 0.7+ = high (80-100)
    if avg_ratio < 0.3:
        return 20 + (avg_ratio / 0.3) * 30
    if avg_ratio < 0.7:
        return 50 + ((avg_ratio - 0.3) / 0.4) * 30
    return 80 + min(20, (avg_ratio - 0.7) * 50)

if __name__ == "__main__":
    # Low velocity: small bodies
    low = [{"open":100, "high":100.3, "low":99.8, "close":100.1}] * 5
    print("Low velocity:", calculate_score(low))
    # High velocity: big bodies
    high = [{"open":100, "high":101.5, "low":99.5, "close":101.4}] * 5
    print("High velocity:", calculate_score(high))
