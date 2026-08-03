"""PositionHeat — portfolio exposure + risk concentration tracking."""
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class HeatSnapshot:
    total_exposure_pct: float   # % of equity
    position_count: int
    heat_score: float           # 0-100: higher = more risky
    reason: str

def calculate(positions: List[Dict], equity: float) -> HeatSnapshot:
    """Calculate portfolio heat score 0-100. Higher = dangerous concentration."""
    if not positions or equity <= 0:
        return HeatSnapshot(0.0, 0, 0.0, "no_positions")

    total_risk = sum(abs(p.get("profit", 0.0)) for p in positions)
    exposure_pct = (total_risk / equity) * 100 if equity > 0 else 0.0

    # Heat scoring
    # <5% exposure → 20-40 (safe)
    # 5-15% → 40-70 (moderate)
    # 15-25% → 70-90 (hot)
    # >25% → 90-100 (danger)
    if exposure_pct < 5:
        heat = 20 + exposure_pct * 4
    elif exposure_pct < 15:
        heat = 40 + (exposure_pct - 5) * 3
    elif exposure_pct < 25:
        heat = 70 + (exposure_pct - 15) * 2
    else:
        heat = min(100, 90 + (exposure_pct - 25))

    reason = f"{len(positions)} pos, {exposure_pct:.1f}% equity"
    return HeatSnapshot(
        total_exposure_pct=round(exposure_pct, 2),
        position_count=len(positions),
        heat_score=min(100, heat),
        reason=reason,
    )

if __name__ == "__main__":
    # Safe: 1 position, low risk
    snap1 = calculate([{"profit": -10}], equity=1000)
    assert snap1.heat_score < 50, f"Expected safe, got {snap1.heat_score}"
    # Hot: 3 positions, 20% equity exposure
    snap2 = calculate([{"profit": -70}, {"profit": -80}, {"profit": -50}], equity=1000)
    assert snap2.heat_score > 70, f"Expected hot, got {snap2.heat_score}"
    print("position_heat OK:", snap1.heat_score, snap2.heat_score)
