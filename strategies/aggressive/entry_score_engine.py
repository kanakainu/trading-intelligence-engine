"""EntryScoreEngine — weighted aggregator. Score >= THRESHOLD = entry."""
from dataclasses import dataclass

THRESHOLD = 60.0  # 2026-08-06: raised from 50, filter out weak pattern=fallback entries

WEIGHTS = {
    "momentum":  0.40,  # primary — trend strength
    "velocity":  0.30,  # conviction — speed matters
    "micro":     0.20,  # M1 structure
    "trend":     0.10,  # M5/H1 regime bias
    # liquidity + vwap dropped — unreliable proxies, drag score ~10%
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
    # Nexus Tweak: Argument conflict detection
    counter_bias_score: float = 50.0,
) -> EntryScore:
    base_score = (
        momentum_score  * WEIGHTS["momentum"]  +
        velocity_score  * WEIGHTS["velocity"]  +
        micro_score     * WEIGHTS["micro"]     +
        trend_score     * WEIGHTS["trend"]
    )
    
    # 🧠 DEBATE LOGIC
    penalty = 0.0
    if counter_bias_score > 70.0:
        penalty = (counter_bias_score - 70.0) * 1.8 # Even harsher for aggressive strategy
        
    score = max(0, base_score - penalty)
    score = round(score, 2)
    
    ok = score >= THRESHOLD and direction in ("BUY", "SELL")
    reason = "ok" if ok else f"score_low:{score:.1f}" if score < THRESHOLD else "no_direction"
    if penalty > 0 and not ok:
        reason = f"debate_block:penalty_{penalty:.1f}"
        
    return EntryScore(score=score, entry_ok=ok, direction=direction, reason=reason)


if __name__ == "__main__":
    r = calculate(80, 70, 75, 60, 65, 70, "BUY")
    assert r.entry_ok, f"Expected entry_ok, got {r}"
    r2 = calculate(20, 20, 20, 20, 20, 20, "BUY")
    assert not r2.entry_ok
    print("EntryScoreEngine OK:", r.score, r2.score)
