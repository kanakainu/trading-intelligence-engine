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
    # BTCUSD is 24/7 - no session restriction
    # Use forex session as proxy for volatility
    if 12 <= h < 16:  return 98, "OVERLAP"
    if 7  <= h < 16:  return 95, "LONDON"
    if 12 <= h < 21:  return 88, "NY"
    # ASIA session - still tradeable for BTCUSD
    return 70, "ASIA_CRYPTO"  # Higher score for crypto

def _tick_speed(candles_m1: List[Dict]) -> float:
    def _h(c,k): return float(c.get(k) or c.get(k.capitalize()) or 0)
    if not candles_m1: return 0.0
    cs = candles_m1[-5:]
    ratios = []
    for c in cs:
        rng = _h(c,"high") - _h(c,"low")
        ratios.append(abs(_h(c,"close") - _h(c,"open"))/rng if rng > 0 else 0)
    return sum(ratios)/len(ratios) if ratios else 0.0

def evaluate(symbol: str, spread: float, atr_m5: float, utc_hour: int,
             candles_m1: List[Dict] = None) -> OpportunitySnapshot:
    session_score, session_name = _session_score(utc_hour)
    tick_speed = _tick_speed(candles_m1 or [])

    # Dynamic thresholds for BTCUSD
    if symbol == "BTCUSD":
        spread_threshold = 1000.0 # BTCUSD spread can be much higher
        atr_min = 10.0 # BTCUSD ATR is higher
        atr_max = 500.0 # BTCUSD ATR can be very high
        tick_speed_min = 0.1 # BTCUSD might have lower tick consistency due to lower vol during consolidation
    else:
        spread_threshold = 30.0 # Default for XAUUSD/GBPJPY
        atr_min = 0.5
        atr_max = 8.0
        tick_speed_min = 0.20

    if session_score < 60:
        return OpportunitySnapshot(OpportunityWindow.CLOSED, f"session={session_name}(score={session_score})", session_score)
    if spread > spread_threshold:
        return OpportunitySnapshot(OpportunityWindow.CLOSED, f"spread={spread}>{spread_threshold}", session_score)
    if atr_m5 > 0 and not (atr_min <= atr_m5 <= atr_max):
        return OpportunitySnapshot(OpportunityWindow.CLOSED, f"atr={atr_m5:.2f} out_of_range[{atr_min}-{atr_max}]", session_score)
    if tick_speed > 0 and tick_speed < tick_speed_min:
        return OpportunitySnapshot(OpportunityWindow.CLOSED, f"tick_speed={tick_speed:.2f}<{tick_speed_min}", session_score)

    score = (session_score * 0.4 + (1 - spread/spread_threshold)*100 * 0.2
             + min(atr_m5/(atr_max/2), 1.0)*100 * 0.2 + tick_speed*100 * 0.2)
    return OpportunitySnapshot(OpportunityWindow.OPEN, f"session={session_name}", min(score, 100))


if __name__ == "__main__":
    def _c(o,h,l,c): return {"open":o,"high":h,"low":l,"close":c}
    cs = [_c(100+i*0.5, 100+i*0.5+0.4, 100+i*0.5-0.1, 100+i*0.5+0.35) for i in range(5)]

    # Test XAUUSD (default values)
    snap_xau = evaluate(symbol="XAUUSD", spread=15, atr_m5=1.5, utc_hour=10, candles_m1=cs)
    assert snap_xau.window == OpportunityWindow.OPEN, f"XAUUSD Expected OPEN got {snap_xau.window}"
    print("XAUUSD opportunity OK:", snap_xau.score)

    # Test BTCUSD with wider ranges
    snap_btc = evaluate(symbol="BTCUSD", spread=500, atr_m5=50.0, utc_hour=10, candles_m1=cs)
    assert snap_btc.window == OpportunityWindow.OPEN, f"BTCUSD Expected OPEN got {snap_btc.window}"
    print("BTCUSD opportunity OK:", snap_btc.score)

    # Test BTCUSD with too wide spread
    snap_btc_closed_spread = evaluate(symbol="BTCUSD", spread=1500, atr_m5=50.0, utc_hour=10, candles_m1=cs)
    assert snap_btc_closed_spread.window == OpportunityWindow.CLOSED, f"BTCUSD (spread) Expected CLOSED got {snap_btc_closed_spread.window}"
    print("BTCUSD (spread) opportunity CLOSED OK")
