"""Attack Engine — SL/TP/lot for C8 entry."""
from dataclasses import dataclass
from typing import List, Dict
from .microstructure import MicroSignal

@dataclass
class AttackPlan:
    lot:     float
    sl:      float
    tp:      float
    comment: str
    rr:      float

SL_BUFFER = 1.5
MIN_TP = 1.5

def _h(c,k): return float(c.get(k) or c.get(k.capitalize()) or 0)

def _swing_pivot(candles_m1, signal):
    """Last 3-bar swing low (BUY) or high (SELL)."""
    cs=candles_m1[-10:] if candles_m1 else []
    if not cs:
        return 0.0  # fallback
    if signal==MicroSignal.BUY:
        lows=[_h(c,"low") for c in cs]
        pivot=min(lows) if lows else 0.0
    else:
        highs=[_h(c,"high") for c in cs]
        pivot=max(highs) if highs else 0.0
    return pivot

def _lot(equity: float) -> float:
    if equity<=400:   return 0.03
    if equity<=1000:  return 0.05
    if equity<=2000:  return 0.10
    if equity<=5000:  return 0.30
    return 0.50

def plan(signal: MicroSignal, entry: float,
         candles_m1: List[Dict], equity: float,
         pattern: str="C8") -> AttackPlan:
    pivot=_swing_pivot(candles_m1, signal)
    if signal==MicroSignal.BUY:
        sl=pivot-SL_BUFFER
        sl_dist=entry-sl
    else:
        sl=pivot+SL_BUFFER
        sl_dist=sl-entry
    sl_dist=max(sl_dist, 0.5)
    tp_dist=max(sl_dist*1.5, MIN_TP)
    tp=entry+tp_dist if signal==MicroSignal.BUY else entry-tp_dist
    rr=round(tp_dist/sl_dist,2)
    return AttackPlan(
        lot=_lot(equity), sl=round(sl,3), tp=round(tp,3),
        comment=f"Riri_C8_{pattern.upper()}", rr=rr
    )


if __name__=="__main__":
    def _c(o,h,l,c): return {"open":o,"high":h,"low":l,"close":c}
    cs=[_c(100+i,101+i,99+i,100.5+i) for i in range(10)]
    p=plan(MicroSignal.BUY, 109.0, cs, equity=500)
    assert p.lot==0.05
    assert p.sl<109.0
    assert p.tp>109.0
    assert "C8" in p.comment
    print("attack_engine OK:", p)
