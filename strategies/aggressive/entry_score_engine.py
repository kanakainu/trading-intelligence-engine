"""EntryScoreEngine — weighted aggregator. Score >= 72 = entry."""
from dataclasses import dataclass

THRESHOLD = 72.0

WEIGHTS = {
    "momentum":   0.30,
    "velocity":   0.20,
    "micro":      0.15,
    "liquidity":  0.15,
    "vwap":       0.10,
    "trend":      0.10,
}

@dataclass
class EntryScore:
    score: float
    entry_ok: bool
    direction: str   # BUY | SELL | NONE
    reason: str

def calculate(
    momentum_score: float,
    velocity_score: float,
    micro_score: float,
    liquidity_score: float,
    vwap_score: float,
    trend_score: float,
    direction: str,
) -> EntryScore:
    score = (
        momentum_score  * WEIGHTS["momentum"]  +
        velocity_score  * WEIGHTS["velocity"]  +
        micro_score     * WEIGHTS["micro"]     +
        liquidity_score * WEIGHTS["liquidity"] +
        vwap_score      * WEIGHTS["vwap"]      +
        trend_score     * WEIGHTS["trend"]
    )
    score = round(score, 2)
    ok = score >= THRESHOLD and direction in ("BUY", "SELL")
    reason = "ok" if ok else f"score_low:{score:.1f}" if score < THRESHOLD else "no_direction"
    return EntryScore(score=score, entry_ok=ok, direction=direction, reason=reason)


if __name__ == "__main__":
    r = calculate(80, 70, 75, 60, 65, 70, "BUY")
    assert r.entry_ok, f"Expected entry_ok, got {r}"
    r2 = calculate(20, 20, 20, 20, 20, 20, "BUY")
    assert not r2.entry_ok
    print("EntryScoreEngine OK:", r.score, r2.score)
