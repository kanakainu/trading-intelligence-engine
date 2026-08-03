"""MarketSnapshot — pure price action state (M1/M5). No gates."""
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class MarketSnapshot:
    momentum_score: float # 0-100
    pattern: str          # Trend pattern
    state: str            # BULL/BEAR/FLAT
    
def snapshot(candles_m5: List[Dict]) -> MarketSnapshot:
    if not candles_m5: return MarketSnapshot(0.0, "NONE", "FLAT")
    # Pure price action score
    last = candles_m5[-1]
    body = abs(last["close"] - last["open"])
    rng = last["high"] - last["low"]
    mom = (body / rng * 100) if rng > 0 else 0
    return MarketSnapshot(round(mom, 2), "EXPANSION", "BULL" if last["close"] > last["open"] else "BEAR")
