"""LiquidityMap — spread and volume profile scoring."""
from typing import List, Dict

def calculate_score(symbol: str, spread: float, candles_m1: List[Dict] = None) -> float:
    """Calculate liquidity score 0-100. Higher = more liquid (lower spread/high vol)."""
    if symbol == "BTCUSD":
        max_spread = 1500.0
    else: # XAUUSD/GBPJPY
        max_spread = 35.0
        
    if spread <= 0: return 50.0
    
    # Spread component: 0-100 (inverse)
    spread_score = max(0, (1 - (spread / max_spread)) * 100)
    
    # Volume component (placeholder for order book / profile)
    # ponytail: add true volume profile score from M1 volume field
    volume_score = 100.0 
    
    # Weighting: 80% spread, 20% volume
    return spread_score * 0.8 + volume_score * 0.2

if __name__ == "__main__":
    print("XAUUSD good spread (12):", calculate_score("XAUUSD", 12))
    print("XAUUSD bad spread (40):", calculate_score("XAUUSD", 40))
    print("BTCUSD spread (600):", calculate_score("BTCUSD", 600))
