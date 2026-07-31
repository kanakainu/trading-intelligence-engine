"""Liquidity Engine — estimates market liquidity from candle-derived proxies.

Inputs: spread, atr, tick_speed (estimated), body_ratio, volume_ratio
Output: LiquidityState (LIKELY_LIQUID | LOW_LIQUIDITY | TOXIC)
"""
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict


class LiquidityState(str, Enum):
    LIKELY_LIQUID = "LIKELY_LIQUID"
    LOW_LIQUIDITY = "LOW_LIQUIDITY"
    TOXIC         = "TOXIC"           # wide spread + dead tick = danger


@dataclass
class LiquiditySnapshot:
    state:        LiquidityState
    score:        float   # 0-100 (higher = more liquid)
    spread_score: float   # 0-100
    atr_score:    float   # 0-100
    tick_score:   float   # 0-100
    body_score:   float   # 0-100
    volume_score: float   # 0-100
    reason:       str


# --- per-pair max spread (price units) -------------------------
MAX_SPREAD = {"XAUUSD": 0.5, "BTCUSD": 50.0, "GBPUSD": 0.0005, "DEFAULT": 1.0}
MIN_ATR    = {"XAUUSD": 0.3, "BTCUSD": 30.0, "GBPUSD": 0.0003, "DEFAULT": 0.1}


def _estimate_tick_speed(candles_m1: List[Dict]) -> float:
    """Estimate tick speed 0-1 from M1 candle body consistency.

    High tick speed = bodies present, price moving each minute.
    Low tick speed = many doji/flat candles = dead market.
    ponytail: real tick feed would give exact ticks/sec; upgrade to MT5 tick stream.
    """
    if not candles_m1:
        return 0.5  # neutral fallback
    n = min(10, len(candles_m1))
    recent = candles_m1[-n:]
    bodies = [abs(float(c["close"]) - float(c["open"])) for c in recent]
    highs  = [float(c["high"]) - float(c["low"]) for c in recent]
    ratios = [b / h if h > 0 else 0.0 for b, h in zip(bodies, highs)]
    return sum(ratios) / len(ratios)   # 0-1: 0=doji, 1=full body


def evaluate_liquidity(
    symbol:       str,
    spread:       float,
    atr:          float,
    candles_m1:   List[Dict],
    volume_ratio: float = 1.0,
) -> LiquiditySnapshot:
    sym = symbol.upper()
    max_sp = MAX_SPREAD.get(sym, MAX_SPREAD["DEFAULT"])
    min_at = MIN_ATR.get(sym, MIN_ATR["DEFAULT"])

    # 1. Spread score — tighter is better
    spread_score = max(0.0, 1.0 - spread / max_sp) * 100

    # 2. ATR score — some volatility needed; too little = dead
    atr_score = min(atr / (min_at * 3), 1.0) * 100 if atr > min_at else (atr / min_at) * 50

    # 3. Tick speed (estimated from M1 body ratio)
    tick_speed   = _estimate_tick_speed(candles_m1)
    tick_score   = tick_speed * 100

    # 4. Body score — large bodies = directional movement
    if candles_m1:
        n = min(5, len(candles_m1))
        brs = []
        for c in candles_m1[-n:]:
            rng = float(c["high"]) - float(c["low"])
            brs.append(abs(float(c["close"]) - float(c["open"])) / rng if rng > 0 else 0)
        body_score = (sum(brs) / len(brs)) * 100
    else:
        body_score = 50.0

    # 5. Volume score
    volume_score = min(volume_ratio / 2.0, 1.0) * 100

    # Weighted composite
    score = (
        spread_score * 0.25
        + atr_score  * 0.20
        + tick_score * 0.25
        + body_score * 0.15
        + volume_score * 0.15
    )

    # Classify
    if spread > max_sp * 1.5 and tick_score < 20:
        state  = LiquidityState.TOXIC
        reason = f"spread={spread:.4f} > 1.5× max + dead tick"
    elif score < 35:
        state  = LiquidityState.LOW_LIQUIDITY
        reason = f"composite={score:.1f} < 35"
    else:
        state  = LiquidityState.LIKELY_LIQUID
        reason = f"composite={score:.1f}"

    return LiquiditySnapshot(
        state=state, score=round(score, 1),
        spread_score=round(spread_score, 1), atr_score=round(atr_score, 1),
        tick_score=round(tick_score, 1), body_score=round(body_score, 1),
        volume_score=round(volume_score, 1), reason=reason,
    )


if __name__ == "__main__":
    # quick self-check
    fake_m1 = [{"open": 100+i, "close": 100+i+0.4, "high": 100+i+0.5, "low": 100+i-0.1}
               for i in range(10)]
    snap = evaluate_liquidity("XAUUSD", spread=0.2, atr=0.6, candles_m1=fake_m1, volume_ratio=1.5)
    assert snap.state == LiquidityState.LIKELY_LIQUID, f"Expected LIKELY_LIQUID, got {snap.state}"
    print(f"OK: {snap.state} score={snap.score}")
