"""Market Pulse Engine — explicit 0-100 market momentum score.

Inputs: impulse_strength, pullback_quality, expansion_score, compression_score
Output: PulseSnapshot (pulse 0-100, verdict)
"""
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class PulseSnapshot:
    pulse:              float   # 0-100 (higher = stronger momentum)
    impulse_score:      float   # 0-100
    pullback_score:     float   # 0-100
    expansion_score:    float   # 0-100
    compression_score:  float   # 0-100 (inverted — compression lowers pulse)
    verdict:            str     # DEAD | WEAK | ACTIVE | EXPLOSIVE


def _impulse(candles_m5: List[Dict]) -> float:
    """Impulse strength = body ratio of last 3 candles, all same direction."""
    if len(candles_m5) < 3:
        return 0.0
    last3 = candles_m5[-3:]
    directions = [1 if float(c["close"]) > float(c["open"]) else -1 for c in last3]
    if len(set(directions)) != 1:
        return 30.0   # mixed candles — some impulse but not clean
    ratios = []
    for c in last3:
        rng = float(c["high"]) - float(c["low"])
        ratios.append(abs(float(c["close"]) - float(c["open"])) / rng if rng > 0 else 0)
    return (sum(ratios) / len(ratios)) * 100


def _pullback_quality(candles_m5: List[Dict]) -> float:
    """Pullback quality = how clean the last retrace is.

    Clean pullback: small body, narrow range, contained within prior candle range.
    """
    if len(candles_m5) < 2:
        return 50.0
    curr = candles_m5[-1]
    prev = candles_m5[-2]
    curr_body = abs(float(curr["close"]) - float(curr["open"]))
    prev_body = abs(float(prev["close"]) - float(prev["open"]))
    curr_rng  = float(curr["high"]) - float(curr["low"]) or 1
    # Clean = small body compared to prev, narrow range
    size_ratio  = 1.0 - min(curr_body / (prev_body + 1e-9), 1.0)
    contained   = 1.0 if (float(curr["high"]) <= float(prev["high"]) and
                           float(curr["low"])  >= float(prev["low"])) else 0.5
    return (size_ratio * 0.6 + contained * 0.4) * 100


def _expansion(candles_m5: List[Dict]) -> float:
    """Expansion = ATR of last 5 vs prior 5 candles."""
    if len(candles_m5) < 10:
        return 50.0
    def avg_rng(cs): return sum(float(c["high"]) - float(c["low"]) for c in cs) / len(cs)
    recent = avg_rng(candles_m5[-5:])
    prior  = avg_rng(candles_m5[-10:-5])
    ratio  = recent / (prior + 1e-9)
    return min(ratio / 2.0, 1.0) * 100   # 2x expansion = 100 score


def _compression(candles_m5: List[Dict]) -> float:
    """Compression = low ATR (squeeze). High compression = bad for scalp.

    Returns 0-100 where 100 = fully compressed (penalizes pulse).
    """
    if len(candles_m5) < 10:
        return 0.0
    def avg_rng(cs): return sum(float(c["high"]) - float(c["low"]) for c in cs) / len(cs)
    recent = avg_rng(candles_m5[-5:])
    prior  = avg_rng(candles_m5[-10:-5])
    ratio  = recent / (prior + 1e-9)
    return max(0.0, (1.0 - ratio) * 100)   # low ratio = compressed


def compute_pulse(candles_m5: List[Dict]) -> PulseSnapshot:
    imp    = _impulse(candles_m5)
    pb     = _pullback_quality(candles_m5)
    exp    = _expansion(candles_m5)
    comp   = _compression(candles_m5)   # penalty

    # Weighted pulse — compression penalizes
    pulse = (
        imp  * 0.35
        + pb * 0.25
        + exp * 0.25
        - comp * 0.15   # penalize squeeze
    )
    pulse = max(0.0, min(100.0, pulse))

    if pulse >= 75:
        verdict = "EXPLOSIVE"
    elif pulse >= 55:
        verdict = "ACTIVE"
    elif pulse >= 35:
        verdict = "WEAK"
    else:
        verdict = "DEAD"

    return PulseSnapshot(
        pulse=round(pulse, 1),
        impulse_score=round(imp, 1),
        pullback_score=round(pb, 1),
        expansion_score=round(exp, 1),
        compression_score=round(comp, 1),
        verdict=verdict,
    )


if __name__ == "__main__":
    # strong trending candles — impulse high, some expansion
    candles = [{"open": 100+i*0.5, "close": 100+i*0.5+0.4, "high": 100+i*0.5+0.5, "low": 100+i*0.5-0.1}
               for i in range(15)]
    snap = compute_pulse(candles)
    assert snap.verdict in ("WEAK", "ACTIVE", "EXPLOSIVE"), f"Expected valid verdict, got {snap.verdict} pulse={snap.pulse}"
    print(f"OK: pulse={snap.pulse} verdict={snap.verdict}")
