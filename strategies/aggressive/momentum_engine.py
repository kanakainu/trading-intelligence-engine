"""MomentumEngine — score-based momentum."""
from typing import List, Dict

def calculate_score(candles_m5: List[Dict]) -> float:
    if len(candles_m5) < 3: return 0.0
    last3 = candles_m5[-3:]
    # Calculate simple body/range momentum
    ratios = []
    for c in last3:
        rng = float(c["high"]) - float(c["low"])
        ratios.append(abs(float(c["close"]) - float(c["open"])) / rng if rng > 0 else 0)
    return min(100.0, (sum(ratios)/len(ratios)) * 100)
