"""MarketSnapshot — pure price action state + score. No gates."""
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
class MarketSnapshot:
    state: MarketState
    score: float        # 0-100: higher = more active/tradeable
    volatility_score: float  # 0-100: range expansion vs avg
    momentum_score: float    # 0-100: directional strength
    reason: str
    timestamp: datetime

def _h(c, k):
    return float(c.get(k) or c.get(k.capitalize()) or c.get(k.upper()) or 0)

def _body(c):  return abs(_h(c, "close") - _h(c, "open"))
def _range(c): return _h(c, "high") - _h(c, "low")
def _br(c):    rng = _range(c); return _body(c) / rng if rng > 0 else 0

def snapshot(candles_m1: List[Dict], candles_m5: List[Dict] = None) -> MarketSnapshot:
    now = datetime.now(timezone.utc)
    if len(candles_m1) < 6:
        return MarketSnapshot(MarketState.SLEEPING, 10, 0, 0, "insufficient_data", now)

    cs = candles_m1

    # Volatility score: how much current bar range vs avg5
    avg5 = sum(_range(c) for c in cs[-6:-1]) / 5 if len(cs) >= 6 else 0
    cur_range = _range(cs[-1])
    vol_ratio = cur_range / (avg5 + 1e-9)
    volatility_score = min(100, vol_ratio * 50)  # 2x avg = 100

    # Momentum score: body ratio of last 3 bars (directional conviction)
    body_ratios = [_br(c) for c in cs[-3:]]
    momentum_score = min(100, sum(body_ratios) / 3 * 100)

    # Directional consistency: same-direction closes
    dirs = [1 if _h(c, "close") > _h(c, "open") else -1 for c in cs[-6:]]
    direction_consistent = all(d == dirs[0] for d in dirs) if len(dirs) >= 6 else False

    # Range contracting
    ranges = [_range(c) for c in cs[-4:]]
    contracting = all(ranges[i] < ranges[i-1] for i in range(1, len(ranges))) if len(ranges) >= 4 else False
    small_body = all(_br(c) < 0.40 for c in cs[-3:])

    # Classify state (kept for context, no longer a gate)
    if avg5 > 0 and cur_range > 1.5 * avg5 and _br(cs[-1]) > 0.60:
        state = MarketState.EXPANDING
        score = min(100, (vol_ratio - 1.0) * 50 + 60)
    elif direction_consistent:
        state = MarketState.TRENDING
        score = 75 + momentum_score * 0.25
    elif contracting and small_body:
        state = MarketState.BUILDING
        score = 40 + volatility_score * 0.2   # building = potential breakout
    else:
        state = MarketState.TRENDING  # default: assume active for XAUUSD
        score = 50 + momentum_score * 0.2

    return MarketSnapshot(
        state=state,
        score=min(100, score),
        volatility_score=volatility_score,
        momentum_score=momentum_score,
        reason=state.value,
        timestamp=now,
    )

# ponytail: candles_m5 unused — add M5 trend filter when multi-tf needed
# Backward compat alias
classify = snapshot

if __name__ == "__main__":
    def _c(o, h, l, c): return {"open": o, "high": h, "low": l, "close": c}
    small = [_c(100+i*0.1, 100+i*0.1+0.2, 100+i*0.1-0.1, 100+i*0.1+0.15) for i in range(5)]
    big = _c(100.5, 102.0, 100.3, 101.9)
    snap = snapshot(small + [big])
    assert snap.state == MarketState.EXPANDING, f"Expected EXPANDING got {snap.state}"
    assert snap.volatility_score > 50, f"Volatility score low: {snap.volatility_score}"
    bulls = [_c(100+i, 100+i+0.8, 100+i-0.1, 100+i+0.7) for i in range(6)]
    snap2 = snapshot(bulls)
    assert snap2.state == MarketState.TRENDING, f"Expected TRENDING got {snap2.state}"
    print("market_snapshot OK — scores:", snap.score, snap.volatility_score, snap.momentum_score)
