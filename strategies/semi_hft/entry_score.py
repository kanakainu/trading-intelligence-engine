"""EntryScore — aggregates engine scores into final entry decision. Score-based, no gates."""
from dataclasses import dataclass
from typing import Optional

# Blueprint weights — rebalanced for live market conditions
W_MOMENTUM   = 0.15  # was 0.20 — drag terbesar
W_VELOCITY   = 0.20  # was 0.15
W_LIQUIDITY  = 0.30  # was 0.25 — paling reliable
W_VOLATILITY = 0.15  # was 0.15
W_PULSE      = 0.05  # was 0.10 — selalu rendah jam segini
W_MICRO      = 0.15  # was 0.15

MIN_ENTRY_SCORE = 60.0  # 2026-08-06: raised from 50, filter out weak pattern=fallback entries

@dataclass
class EntryScore:
    score: float          # 0-100 final weighted
    direction: str        # "BUY" | "SELL" | "NONE"
    pattern: str
    breakdown: dict       # {engine: score} for debugging
    entry_ok: bool        # score >= MIN_ENTRY_SCORE AND direction != NONE

def calculate(
    momentum_score: float,    # from micro_momentum_engine (0-100)
    velocity_score: float,    # from tick_velocity_engine (0-100)
    liquidity_score: float,   # from liquidity_map (0-100)
    volatility_score: float,  # from volatility_engine (0-100)
    pulse_score: float,       # from market_pulse_engine (0-100)
    micro_score: float,       # from micro_momentum_engine.score (0-100)
    direction: str,           # "BUY" | "SELL" | "NONE"
    pattern: str = "",
    # Nexus Tweak: Counter-argument scores to detect conflict
    counter_bias_score: float = 50.0, # 0-100. If 100 for BUY, it means "Extreme BEARISH case"
) -> EntryScore:
    base_score = (
        momentum_score   * W_MOMENTUM +
        velocity_score   * W_VELOCITY +
        liquidity_score  * W_LIQUIDITY +
        volatility_score * W_VOLATILITY +
        pulse_score      * W_PULSE +
        micro_score      * W_MICRO
    )
    
    # 🧠 DEBATE LOGIC (A5 vs A6 style)
    # If counter_bias is high (> 70), penalty base score
    penalty = 0.0
    if counter_bias_score > 70.0:
        penalty = (counter_bias_score - 70.0) * 1.5 # Harsh penalty for strong counter arguments
    
    score = max(0, base_score - penalty)
    
    entry_ok = score >= MIN_ENTRY_SCORE and direction != "NONE"
    return EntryScore(
        score=round(score, 2),
        direction=direction,
        pattern=pattern,
        breakdown={
            "momentum": momentum_score, "velocity": velocity_score,
            "liquidity": liquidity_score, "volatility": volatility_score,
            "pulse": pulse_score, "micro": micro_score,
            "debate_penalty": round(penalty, 2)
        },
        entry_ok=entry_ok,
    )

if __name__ == "__main__":
    # All high scores → entry OK
    e = calculate(85, 80, 90, 75, 80, 82, "BUY", "breakout")
    assert e.entry_ok, f"Expected entry_ok, score={e.score}"
    assert e.score >= 75
    # Low momentum → reject
    e2 = calculate(40, 50, 90, 75, 80, 82, "BUY", "weak")
    assert not e2.entry_ok, f"Expected reject, score={e2.score}"
    print("entry_score OK:", e.score, e.direction)
