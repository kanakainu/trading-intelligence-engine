"""Opportunity Engine — spread/liquidity/volatility/session gate."""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict

class OpportunityWindow(Enum):
    OPEN   = "open"
    CLOSED = "closed"

@dataclass
class OpportunitySnapshot:
    window: OpportunityWindow
    reason: str
    score: float   # 0-100

def _session_score(utc_hour: int) -> tuple:
    h = utc_hour
    if 12 <= h < 16:  return 98, "OVERLAP"
    if 7  <= h < 16:  return 95, "LONDON"
    if 12 <= h < 21:  return 88, "NY"
    return 20, "ASIA"

def _tick_speed(candles_m1: List[Dict]) -> float:
    def _h(c,k): return float(c.get(k) or c.get(k.capitalize()) or 0)
    if not candles_m1: return 0.0
    cs = candles_m1[-5:]
    ratios = []
    for c in cs:
        rng = _h(c,"high") - _h(c,"low")
        ratios.append(abs(_h(c,"close") - _h(c,"open"))/rng if rng > 0 else 0)
    return sum(ratios)/len(ratios) if ratios else 0.0

def evaluate(spread: float, atr_m5: float, utc_hour: int,
             candles_m1: List[Dict] = None) -> OpportunitySnapshot:
    session_score, session_name = _session_score(utc_hour)
    tick_speed = _tick_speed(candles_m1 or [])

    if session_score < 60:
        return OpportunitySnapshot(OpportunityWindow.CLOSED, f"session={session_name}(score={session_score})", session_score)
    if spread > 30:
        return OpportunitySnapshot(OpportunityWindow.CLOSED, f"spread={spread}>30", session_score)
    if not (0.5 <= atr_m5 <= 4.0):
        return OpportunitySnapshot(OpportunityWindow.CLOSED, f"atr={atr_m5:.2f} out_of_range[0.5-4.0]", session_score)
    if tick_speed < 0.30:
        return OpportunitySnapshot(OpportunityWindow.CLOSED, f"tick_speed={tick_speed:.2f}<0.30", session_score)

    score = (session_score * 0.4 + (1 - spread/30)*100 * 0.2
             + min(atr_m5/4.0, 1.0)*100 * 0.2 + tick_speed*100 * 0.2)
    return OpportunitySnapshot(OpportunityWindow.OPEN, f"session={session_name}", min(score, 100))


if __name__ == "__main__":
    def _c(o,h,l,c): return {"open":o,"high":h,"low":l,"close":c}
    cs = [_c(100+i*0.5, 100+i*0.5+0.4, 100+i*0.5-0.1, 100+i*0.5+0.35) for i in range(5)]
    snap = evaluate(spread=15, atr_m5=1.5, utc_hour=10, candles_m1=cs)
    assert snap.window == OpportunityWindow.OPEN, f"Expected OPEN got {snap.window}"
    snap2 = evaluate(spread=15, atr_m5=1.5, utc_hour=3, candles_m1=cs)
    assert snap2.window == OpportunityWindow.CLOSED
    print("opportunity OK:", snap.score)
