"""VelocityEngine — price acceleration score 0-100."""
from typing import List, Dict

def _rng(c): return float(c["high"]) - float(c["low"])
def _body(c): return abs(float(c["close"]) - float(c["open"]))

def calculate_score(candles_m5: List[Dict], atr: float = 0.0) -> float:
    if len(candles_m5) < 3: return 0.0
    last3 = candles_m5[-3:]
    avg_body = sum(_body(c) for c in last3) / 3
    ref = atr if atr > 0 else (sum(_rng(c) for c in last3) / 3)
    if ref == 0: return 0.0
    return min(100.0, (avg_body / ref) * 100)
