"""Micro Exit Engine — priority exit checks."""
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict

class ExitAction(Enum):
    HOLD    = "hold"
    PARTIAL = "partial"
    CLOSE   = "close"

@dataclass
class ExitSignal:
    reason:  str
    urgency: float   # 0-1
    action:  ExitAction

def _h(c,k): return float(c.get(k) or c.get(k.capitalize()) or 0)
def _br(c):
    rng=_h(c,"high")-_h(c,"low")
    return abs(_h(c,"close")-_h(c,"open"))/rng if rng>0 else 0

def evaluate(current: float, tp: float, sl: float, direction: str,
             entry_spread: float, current_spread: float,
             hold_seconds: float, candles_m1: List[Dict]) -> ExitSignal:

    sign=1 if direction=="BUY" else -1

    # 1. TP hit
    if (direction=="BUY"  and current>=tp) or \
       (direction=="SELL" and current<=tp):
        return ExitSignal("tp_hit", 1.0, ExitAction.CLOSE)

    # 2. SL hit
    if (direction=="BUY"  and current<=sl) or \
       (direction=="SELL" and current>=sl):
        return ExitSignal("sl_hit", 1.0, ExitAction.CLOSE)

    # 3. Momentum fade: last 2 bars body/range < 0.25
    if len(candles_m1)>=2:
        fade=all(_br(c)<0.25 for c in candles_m1[-2:])
        if fade:
            return ExitSignal("momentum_fade", 0.75, ExitAction.PARTIAL)

    # 4. Liquidity collapse: spread > 2× entry
    if entry_spread>0 and current_spread>2*entry_spread:
        return ExitSignal("liquidity_collapse", 0.90, ExitAction.CLOSE)

    # 5. Velocity death: avg body/range < 0.15
    if candles_m1:
        avg_br=sum(_br(c) for c in candles_m1[-5:])/min(len(candles_m1),5)
        if avg_br<0.15:
            return ExitSignal("velocity_death", 0.80, ExitAction.CLOSE)

    # 6. TimeStop
    if hold_seconds>360:
        return ExitSignal("time_stop", 0.70, ExitAction.CLOSE)

    return ExitSignal("hold", 0.0, ExitAction.HOLD)


if __name__=="__main__":
    def _c(o,h,l,c): return {"open":o,"high":h,"low":l,"close":c}
    cs=[_c(100,100.5,99.5,100.3) for _ in range(5)]
    r=evaluate(100.5,102.0,99.0,"BUY",15,15,30,cs)
    assert r.action==ExitAction.HOLD
    r2=evaluate(102.1,102.0,99.0,"BUY",15,15,30,cs)
    assert r2.action==ExitAction.CLOSE and r2.reason=="tp_hit"
    print("exit_engine OK:", r2.reason)
