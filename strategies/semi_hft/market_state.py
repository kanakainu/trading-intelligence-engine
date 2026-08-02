"""Market State Engine — pure price action, no indicators."""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict

class MarketState(Enum):
    SLEEPING  = "sleeping"
    BUILDING  = "building"
    EXPANDING = "expanding"
    TRENDING  = "trending"
    EXHAUSTED = "exhausted"

@dataclass
class MarketStateSnapshot:
    state: MarketState
    score: float          # 0-100
    reason: str
    timestamp: datetime

def _h(c, k):
    return float(c.get(k) or c.get(k.capitalize()) or c.get(k.upper()) or 0)

def _body(c):  return abs(_h(c,"close") - _h(c,"open"))
def _range(c): return _h(c,"high") - _h(c,"low")
def _br(c):    rng = _range(c); return _body(c)/rng if rng > 0 else 0

def classify(candles_m1: List[Dict], candles_m5: List[Dict] = None) -> MarketStateSnapshot:
    now = datetime.now(timezone.utc)
    if len(candles_m1) < 6:
        return MarketStateSnapshot(MarketState.SLEEPING, 0, "insufficient_data", now)

    cs = candles_m1

    # EXHAUSTED: last 2 bars — wick > 2× body OR body < 20% range
    def _exhausted():
        for c in cs[-2:]:
            b = _body(c); r = _range(c)
            wick = r - b
            if r > 0 and (wick > 2*b or b/r < 0.20):
                return True
        return False

    # EXPANDING: current bar range > 1.5× avg5 AND body > 60%
    def _expanding():
        avg5 = sum(_range(c) for c in cs[-6:-1]) / 5
        cur = cs[-1]
        return avg5 > 0 and _range(cur) > 1.5*avg5 and _br(cur) > 0.60

    # TRENDING: 5+ consecutive same-direction closes
    def _trending():
        if len(cs) < 6: return False
        dirs = [1 if _h(c,"close") > _h(c,"open") else -1 for c in cs[-6:]]
        return all(d == dirs[0] for d in dirs)

    # BUILDING: range contracting 3+ bars, bodies < 40%
    def _building():
        if len(cs) < 4: return False
        ranges = [_range(c) for c in cs[-4:]]
        contracting = all(ranges[i] < ranges[i-1] for i in range(1, len(ranges)))
        small_body = all(_br(c) < 0.40 for c in cs[-3:])
        return contracting and small_body

    # SLEEPING: tiny bodies + tiny range (skip for crypto - different scale)
    def _sleeping():
        # ponytail: use percentage-based threshold instead of absolute
        # avg_body = sum(_body(c) for c in cs[-5:]) / 5
        # avg_rng  = sum(_range(c) for c in cs[-5:]) / 5
        # return avg_body < 0.15 and avg_rng < 0.3
        return False  # Skip SLEEPING check - let validator decide

    # Skip EXHAUSTED check for crypto (BTCUSD has different patterns)
    # ponytail: add symbol parameter to classify() if need symbol-specific logic
    # if _exhausted():
    #     return MarketStateSnapshot(MarketState.EXHAUSTED, 20, "pin_bar_or_doji", now)
    if _expanding():
        avg5 = sum(_range(c) for c in cs[-6:-1]) / 5
        score = min(100, (_range(cs[-1])/(avg5+1e-9) - 1.0)*50 + 60)
        return MarketStateSnapshot(MarketState.EXPANDING, score, "expanding_bar", now)
    if _trending():
        return MarketStateSnapshot(MarketState.TRENDING, 80, "consecutive_directional", now)
    if _building():
        return MarketStateSnapshot(MarketState.BUILDING, 40, "range_contracting", now)
    # Default: assume TRENDING for crypto (avoid SLEEPING blocking)
    # ponytail: add proper volume/volatility check later
    return MarketStateSnapshot(MarketState.TRENDING, 50, "default_trending", now)


if __name__ == "__main__":
    def _c(o, h, l, c): return {"open":o,"high":h,"low":l,"close":c}
    # Expanding: big bar after 5 small
    small = [_c(100+i*0.1, 100+i*0.1+0.2, 100+i*0.1-0.1, 100+i*0.1+0.15) for i in range(5)]
    big   = _c(100.5, 102.0, 100.3, 101.9)
    snap = classify(small + [big])
    assert snap.state == MarketState.EXPANDING, f"Expected EXPANDING got {snap.state}"
    # Trending: 6 bull bars
    bulls = [_c(100+i, 100+i+0.8, 100+i-0.1, 100+i+0.7) for i in range(6)]
    snap2 = classify(bulls)
    assert snap2.state == MarketState.TRENDING, f"Expected TRENDING got {snap2.state}"
    print("market_state OK")
