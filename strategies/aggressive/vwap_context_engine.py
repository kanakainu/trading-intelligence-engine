"""VWAPContextEngine — price proximity to VWAP → score 0-100."""
from typing import Optional

def calculate_score(price: float, vwap: Optional[float]) -> float:
    """Closer to VWAP = higher score. No VWAP = neutral 50."""
    if not vwap or vwap <= 0: return 50.0
    dist_pct = abs(price - vwap) / vwap
    # <0.1% = 100, 1% = 0
    score = max(0.0, 100.0 - (dist_pct / 0.01) * 100)
    return round(min(100.0, score), 2)
