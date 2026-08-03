"""VolatilityEngine — adaptive volatility scoring."""
from typing import List, Dict

def _h(c, k): return float(c.get(k) or c.get(k.capitalize()) or 0)

def calculate_score(symbol: str, atr_m5: float) -> float:
    """Calculate volatility score 0-100. Higher = better for scalping."""
    if symbol == "BTCUSD":
        min_v = 10.0
        max_v = 300.0
    else: # XAUUSD/GBPJPY
        min_v = 0.4
        max_v = 10.0
    
    if atr_m5 <= 0: return 50.0 # neutral
    
    if atr_m5 < min_v:
        # Too low: score 0-40
        return min(40, (atr_m5 / min_v) * 40)
    if atr_m5 > max_v:
        # Too high (volatile): score 100-70 (diminishing return)
        return max(70, 100 - ((atr_m5 - max_v) / max_v) * 30)
    
    # Sweet spot: 60-100
    ratio = (atr_m5 - min_v) / (max_v - min_v)
    return 60 + ratio * 40

if __name__ == "__main__":
    print("XAUUSD low vol (0.2):", calculate_score("XAUUSD", 0.2))
    print("XAUUSD sweet spot (1.5):", calculate_score("XAUUSD", 1.5))
    print("XAUUSD high vol (20):", calculate_score("XAUUSD", 20))
    print("BTCUSD sweet spot (150):", calculate_score("BTCUSD", 150))
