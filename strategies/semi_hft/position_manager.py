"""Fast Position Manager — BE, partial, trail, velocity, time stop."""
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict

class PositionAction(Enum):
    HOLD           = "hold"
    MOVE_BE        = "move_be"
    TRAIL          = "trail"
    PARTIAL        = "partial"
    CLOSE_TIME     = "close_time"
    CLOSE_VELOCITY = "close_velocity"

@dataclass
class PositionDecision:
    action:  PositionAction
    new_sl:  float = 0.0
    reason:  str   = ""

BE_TRIGGER  = 0.8   # pts profit to move BE
PART_TRIGGER= 1.2   # pts profit to partial 50%
TRAIL_DIST  = 0.5   # trail distance after BE
MAX_HOLD    = 360   # seconds
VEL_THRESH  = 0.15  # tick_speed below this = velocity death

def _h(c,k): return float(c.get(k) or c.get(k.capitalize()) or 0)
def _tick_speed(cs):
    if not cs: return 1.0
    ratios=[]
    for c in cs[-5:]:
        rng=_h(c,"high")-_h(c,"low")
        ratios.append(abs(_h(c,"close")-_h(c,"open"))/rng if rng>0 else 0)
    return sum(ratios)/len(ratios) if ratios else 0.0

def evaluate(entry: float, current: float, sl: float, direction: str,
             hold_seconds: float, candles_m1: List[Dict],
             be_moved: bool=False) -> PositionDecision:
    sign = 1 if direction=="BUY" else -1
    profit = (current-entry)*sign

    # Time stop
    if hold_seconds >= MAX_HOLD:
        return PositionDecision(PositionAction.CLOSE_TIME, reason="max_hold")

    # Velocity death
    if _tick_speed(candles_m1) < VEL_THRESH:
        return PositionDecision(PositionAction.CLOSE_VELOCITY, reason="velocity_death")

    # Partial at +1.2pt
    if profit >= PART_TRIGGER and not be_moved:
        return PositionDecision(PositionAction.PARTIAL, reason="partial_1.2pt")

    # BE at +0.8pt
    if profit >= BE_TRIGGER and not be_moved:
        return PositionDecision(PositionAction.MOVE_BE, new_sl=entry, reason="move_be")

    # Trail after BE
    if be_moved:
        trail_sl = current - TRAIL_DIST*sign
        if (direction=="BUY" and trail_sl>sl) or (direction=="SELL" and trail_sl<sl):
            return PositionDecision(PositionAction.TRAIL, new_sl=round(trail_sl,3), reason="trail")

    return PositionDecision(PositionAction.HOLD, reason="hold")


if __name__=="__main__":
    def _c(o,h,l,c): return {"open":o,"high":h,"low":l,"close":c}
    cs=[_c(100+i*0.5,100+i*0.5+0.4,100+i*0.5-0.1,100+i*0.5+0.35) for i in range(5)]
    d=evaluate(100.0, 101.0, 98.5, "BUY", 30, cs, be_moved=False)
    assert d.action==PositionAction.MOVE_BE, d
    d2=evaluate(100.0, 100.0, 98.5, "BUY", 400, cs, be_moved=False)
    assert d2.action==PositionAction.CLOSE_TIME
    print("position_manager OK:", d.action)
