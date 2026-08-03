"""MarketPulseEngine — detecting market 'heartbeat' (volume/range spikes)."""
from typing import List, Dict

def _h(c, k): return float(c.get(k) or c.get(k.capitalize()) or 0)
def _range(c): return _h(c, "high") - _h(c, "low")

def calculate_score(candles_m1: List[Dict]) -> float:
    """Calculate pulse score 0-100. Higher = market is 'alive'."""
    if len(candles_m1) < 10: return 50.0
    
    # Pulse = current range vs avg of last 10
    avg_range = sum(_range(c) for c in candles_m1[-11:-1]) / 10
    current_range = _range(candles_m1[-1])
    
    if avg_range <= 0: return 50.0
    
    ratio = current_range / avg_range
    
    # Score mapping:
    # 1.0 (normal) -> 50
    # 2.0 (spike) -> 80
    # 3.0+ (extreme) -> 100
    if ratio < 1.0:
        return max(20, ratio * 50)
    
    score = 50 + (ratio - 1.0) * 30
    return min(100, score)

if __name__ == "__main__":
    print("Normal Pulse (ratio 1.0):", calculate_score([{"high":101,"low":100}]*11))
    print("Spike Pulse (ratio 2.0):", calculate_score([{"high":101,"low":100}]*10 + [{"high":102,"low":100}]))
