"""MicroMomentumEngine — 5 price action patterns, score-based (0-100). No indicators."""
from dataclasses import dataclass
from typing import List, Dict
from enum import Enum

class MicroSignal(Enum):
    BUY  = "BUY"
    SELL = "SELL"
    NONE = "NONE"

@dataclass
class MicroMomentumSnapshot:
    signal:  MicroSignal
    score:   float    # 0-100 (was quality 0-1)
    pattern: str
    reason:  str

def _h(c, k): return float(c.get(k) or c.get(k.capitalize()) or 0)
def _body(c):  return abs(_h(c, "close") - _h(c, "open"))
def _range(c): return max(_h(c, "high") - _h(c, "low"), 1e-9)
def _br(c):    return _body(c) / _range(c)
def _dir(c):   return 1 if _h(c, "close") > _h(c, "open") else -1

def _breakout(cs):
    if len(cs) < 7: return MicroSignal.NONE, 0.0
    window = cs[-6:-1]; cur = cs[-1]
    avg5 = sum(_range(c) for c in window) / 5
    hi = max(_h(c, "high") for c in window)
    lo = min(_h(c, "low") for c in window)
    if _h(cur, "close") > hi:
        q = min((_h(cur, "close") - hi) / avg5, 1.0)
        return MicroSignal.BUY, q * 100
    if _h(cur, "close") < lo:
        q = min((lo - _h(cur, "close")) / avg5, 1.0)
        return MicroSignal.SELL, q * 100
    return MicroSignal.NONE, 0.0

def _swing_break(cs):
    if len(cs) < 10: return MicroSignal.NONE, 0.0
    cur = cs[-1]
    pivots_hi = []; pivots_lo = []
    for i in range(1, len(cs) - 2):
        if _h(cs[i], "high") > _h(cs[i-1], "high") and _h(cs[i], "high") > _h(cs[i+1], "high"):
            pivots_hi.append(_h(cs[i], "high"))
        if _h(cs[i], "low") < _h(cs[i-1], "low") and _h(cs[i], "low") < _h(cs[i+1], "low"):
            pivots_lo.append(_h(cs[i], "low"))
    if pivots_hi and _h(cur, "close") > pivots_hi[-1]:
        return MicroSignal.BUY, _br(cur) * 100
    if pivots_lo and _h(cur, "close") < pivots_lo[-1]:
        return MicroSignal.SELL, _br(cur) * 100
    return MicroSignal.NONE, 0.0

def _pullback(cs):
    if len(cs) < 8: return MicroSignal.NONE, 0.0
    move = _h(cs[-4], "close") - _h(cs[-8], "close")
    if abs(move) < 1e-6: return MicroSignal.NONE, 0.0
    retrace = (_h(cs[-4], "close") - _h(cs[-1], "close")) / abs(move)
    cur = cs[-1]; br = _br(cur)
    if move > 0 and 0 < retrace <= 0.50 and br > 0.60:
        return MicroSignal.BUY, (1 - retrace) * br * 100
    if move < 0 and 0 < retrace <= 0.50 and br > 0.60:
        return MicroSignal.SELL, (1 - retrace) * br * 100
    return MicroSignal.NONE, 0.0

def _expansion(cs):
    if len(cs) < 6: return MicroSignal.NONE, 0.0
    avg5 = sum(_range(c) for c in cs[-6:-1]) / 5; cur = cs[-1]
    if avg5 == 0: return MicroSignal.NONE, 0.0
    ratio = _range(cur) / avg5; br = _br(cur)
    if ratio > 1.3 and br > 0.55:
        sig = MicroSignal.BUY if _dir(cur) == 1 else MicroSignal.SELL
        return sig, min((ratio - 1.0) * br * 100, 100.0)
    return MicroSignal.NONE, 0.0

def _impulse(cs):
    if len(cs) < 4: return MicroSignal.NONE, 0.0
    streak = 0; d = _dir(cs[-1])
    for c in reversed(cs[-5:]):
        if _dir(c) == d: streak += 1
        else: break
    if streak < 3: return MicroSignal.NONE, 0.0
    avg_br = sum(_br(c) for c in cs[-streak:]) / streak
    if avg_br < 0.50: return MicroSignal.NONE, 0.0
    return (MicroSignal.BUY if d == 1 else MicroSignal.SELL), avg_br * 100

def calculate_score(candles_m1: List[Dict]) -> MicroMomentumSnapshot:
    """Detect best micro pattern, return score 0-100."""
    cs = candles_m1
    results = [
        ("breakout",    _breakout(cs)),
        ("swing_break", _swing_break(cs)),
        ("pullback",    _pullback(cs)),
        ("expansion",   _expansion(cs)),
        ("impulse",     _impulse(cs)),
    ]
    best = max(results, key=lambda x: x[1][1])
    name, (sig, score) = best

    if sig == MicroSignal.NONE or score < 1.0:
        # Weak fallback: use last bar direction (minimum signal)
        if cs:
            last_br = _br(cs[-1])
            if last_br > 0.01:
                sig = MicroSignal.BUY if _dir(cs[-1]) == 1 else MicroSignal.SELL
                score = max(last_br * 20, 5.0)  # max 20 for fallback
                return MicroMomentumSnapshot(sig, score, "fallback", f"fallback score={score:.1f}")
        return MicroMomentumSnapshot(MicroSignal.NONE, 0.0, "none", "no_pattern")

    return MicroMomentumSnapshot(sig, min(score, 100.0), name, f"{name} score={score:.1f}")

if __name__ == "__main__":
    def _c(o, h, l, c): return {"open": o, "high": h, "low": l, "close": c}
    small = [_c(100+i*0.1, 100+i*0.1+0.2, 100+i*0.1-0.1, 100+i*0.1+0.15) for i in range(5)]
    big = _c(100.5, 102.5, 100.4, 102.3)
    snap = calculate_score(small * 2 + [big])
    assert snap.signal == MicroSignal.BUY, snap
    assert snap.score > 50, f"Score too low: {snap.score}"
    print("micro_momentum OK:", snap.pattern, f"score={snap.score:.1f}")
