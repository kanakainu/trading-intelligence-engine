"""TriggerEngine — M1 timing only. NOT market direction thesis.
M15/M5 decide direction. M1 decides WHEN to enter.
"""
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict


class TriggerSignal(str, Enum):
    ARMED = "ARMED"
    WAIT  = "WAIT"
    NONE  = "NONE"


def _get(c: Dict, *keys, default=0.0) -> float:
    for k in keys:
        v = c.get(k)
        if v is not None:
            try: return float(v)
            except (ValueError, TypeError): pass
    return default


@dataclass
class TriggerResult:
    signal:    TriggerSignal
    strength:  float          # 0–25
    direction: str            # BUY | SELL | NONE
    reason:    str


def _strength(body: float, atr: float) -> float:
    if atr <= 0: return 0.0
    ratio = body / atr
    if ratio >= 0.8: return 25.0
    if ratio >= 0.5: return 17.0
    if ratio >= 0.3: return 10.0
    return 0.0


def evaluate(
    direction:  str,          # expected direction from setup (BUY/SELL)
    candles_m1: List[Dict],
    atr_m1:     float,
) -> TriggerResult:
    cs = [c for c in candles_m1 if c]
    if len(cs) < 3:
        return TriggerResult(TriggerSignal.NONE, 0.0, "NONE", "insufficient_m1_candles")

    c0 = cs[-1]   # last candle
    c1 = cs[-2]   # prev candle

    o0 = _get(c0, "open",  "Open")
    cl0 = _get(c0, "close", "Close")
    cl1 = _get(c1, "close", "Close")
    body = abs(cl0 - o0)

    if direction == "BUY":
        bullish = cl0 > o0                      # green candle
        above_prev = cl0 > cl1                  # closed above previous close
        big_enough = body >= 0.3 * atr_m1 if atr_m1 > 0 else body > 0
        if bullish and above_prev and big_enough:
            return TriggerResult(TriggerSignal.ARMED, _strength(body, atr_m1),
                                 "BUY", f"m1_bull body={body:.2f} atr={atr_m1:.2f}")
        return TriggerResult(TriggerSignal.WAIT, 0.0, "BUY",
                             f"trigger_wait bull={bullish} above={above_prev} body={body:.2f}")

    elif direction == "SELL":
        bearish = cl0 < o0
        below_prev = cl0 < cl1
        big_enough = body >= 0.3 * atr_m1 if atr_m1 > 0 else body > 0
        if bearish and below_prev and big_enough:
            return TriggerResult(TriggerSignal.ARMED, _strength(body, atr_m1),
                                 "SELL", f"m1_bear body={body:.2f} atr={atr_m1:.2f}")
        return TriggerResult(TriggerSignal.WAIT, 0.0, "SELL",
                             f"trigger_wait bear={bearish} below={below_prev} body={body:.2f}")

    return TriggerResult(TriggerSignal.NONE, 0.0, "NONE", "no_direction")
