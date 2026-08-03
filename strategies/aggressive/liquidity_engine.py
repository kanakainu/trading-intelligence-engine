"""LiquidityEngine — volume ratio + S/R proximity score 0-100."""
from typing import List, Dict

def calculate_score(volume_ratio: float, near_level: bool = False) -> float:
    """High volume_ratio + near S/R = higher liquidity score."""
    vol_score = min(100.0, volume_ratio * 50)  # 2.0 ratio = 100
    level_bonus = 20.0 if near_level else 0.0
    return min(100.0, vol_score + level_bonus)
