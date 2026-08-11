"""FastRisk — SL/TP/lot calculation. Only hard-reject engine (invalid SL/equity)."""
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class RiskPlan:
    lot:     float
    sl:      float
    tp:      float
    comment: str
    rr:      float
    valid:   bool
    reason:  str

from detectors.common import sl_buffer

MIN_TP    = 1.5

def _h(c, k): return float(c.get(k) or c.get(k.capitalize()) or 0)

def _swing_pivot(candles_m1: List[Dict], direction: str) -> float:
    """Last swing low (BUY) or high (SELL) from last 10 bars."""
    cs = candles_m1[-10:] if candles_m1 else []
    if not cs: return 0.0
    if direction == "BUY":
        return min(_h(c, "low") for c in cs)
    return max(_h(c, "high") for c in cs)

def _lot(equity: float) -> float:
    # Match DynamicLotPlugin tiers — single source of truth
    if equity < 2000: return 0.01
    if equity < 5000: return 0.02
    return 0.05

def plan(direction: str, entry: float,
         candles_m1: List[Dict], equity: float,
         pattern: str = "C8") -> RiskPlan:
    """Calculate SL/TP/lot. Returns valid=False only if equity=0 or entry=0."""
    if not entry or not equity:
        return RiskPlan(0, 0, 0, "invalid", 0, False, "entry/equity=0")

    pivot = _swing_pivot(candles_m1, direction)
    if pivot <= 0:
        return RiskPlan(0, 0, 0, "invalid", 0, False, "no swing pivot")

    _sl_buffer = sl_buffer(context=None) # ponytail: context from strategy
    if direction == "BUY":
        sl = pivot - _sl_buffer
        sl_dist = max(entry - sl, 0.5)
    else:
        sl = pivot + _sl_buffer
        sl_dist = max(sl - entry, 0.5)

    tp_dist = max(sl_dist * 1.5, MIN_TP)
    tp = entry + tp_dist if direction == "BUY" else entry - tp_dist
    rr = round(tp_dist / sl_dist, 2)

    return RiskPlan(
        lot=_lot(equity), sl=round(sl, 3), tp=round(tp, 3),
        comment=f"SemiHFT_V4_{pattern.upper()}", rr=rr,
        valid=True, reason="ok",
    )

if __name__ == "__main__":
    def _c(o, h, l, c): return {"open": o, "high": h, "low": l, "close": c}
    cs = [_c(100+i, 101+i, 99+i, 100.5+i) for i in range(10)]
    p = plan("BUY", 109.0, cs, equity=500)
    assert p.valid
    assert p.lot == 0.05
    assert p.sl < 109.0
    assert p.tp > 109.0
    assert p.rr >= 1.5
    print("fast_risk OK:", p)
