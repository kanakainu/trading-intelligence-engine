"""ExitIntelligence — momentum/liquidity/velocity monitoring. Score-based (0-100)."""
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class ExitSignal:
    exit_score: float    # 0-100: higher = stronger exit signal
    reason: str
    urgency: float       # 0-1: how fast to act

def _h(c, k): return float(c.get(k) or c.get(k.capitalize()) or 0)
def _br(c):
    rng = _h(c, "high") - _h(c, "low")
    return abs(_h(c, "close") - _h(c, "open")) / rng if rng > 0 else 0

def evaluate(current: float, tp: float, sl: float, direction: str,
             entry_spread: float, current_spread: float,
             hold_seconds: float, candles_m1: List[Dict]) -> ExitSignal:
    """Exit intelligence: score 0-100. Higher = close position NOW."""
    scores = []

    # TP hit → 100
    if (direction == "BUY" and current >= tp) or (direction == "SELL" and current <= tp):
        return ExitSignal(100.0, "tp_hit", 1.0)

    # SL hit → 100
    if (direction == "BUY" and current <= sl) or (direction == "SELL" and current >= sl):
        return ExitSignal(100.0, "sl_hit", 1.0)

    # Momentum fade: last 2 bars body/range < 0.25
    if len(candles_m1) >= 2:
        fade = all(_br(c) < 0.25 for c in candles_m1[-2:])
        if fade:
            scores.append(("momentum_fade", 75, 0.75))

    # Liquidity collapse: spread > 2× entry
    if entry_spread > 0 and current_spread > 2 * entry_spread:
        ratio = current_spread / entry_spread
        collapse_score = min(100, 50 + (ratio - 2.0) * 25)
        scores.append(("liquidity_collapse", collapse_score, 0.90))

    # Velocity death: avg body/range < 0.15
    if candles_m1:
        avg_br = sum(_br(c) for c in candles_m1[-5:]) / min(len(candles_m1), 5)
        if avg_br < 0.15:
            death_score = max(0, (0.15 - avg_br) / 0.15 * 80)
            scores.append(("velocity_death", death_score, 0.80))

    # Time stop: >360s
    if hold_seconds > 360:
        time_score = min(100, 50 + (hold_seconds - 360) / 600 * 50)
        scores.append(("time_stop", time_score, 0.70))

    if not scores:
        return ExitSignal(0.0, "hold", 0.0)

    # Pick highest score
    best = max(scores, key=lambda x: x[1])
    return ExitSignal(best[1], best[0], best[2])

if __name__ == "__main__":
    def _c(o, h, l, c): return {"open": o, "high": h, "low": l, "close": c}
    cs = [_c(100, 100.5, 99.5, 100.3) for _ in range(5)]
    r = evaluate(100.5, 102.0, 99.0, "BUY", 15, 15, 30, cs)
    assert r.exit_score == 0.0, f"Expected hold, got {r.exit_score}"
    r2 = evaluate(102.1, 102.0, 99.0, "BUY", 15, 15, 30, cs)
    assert r2.exit_score == 100.0 and r2.reason == "tp_hit"
    print("exit_intelligence OK:", r2.reason, f"score={r2.exit_score}")
