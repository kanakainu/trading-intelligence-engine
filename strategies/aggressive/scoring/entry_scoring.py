"""Entry Scoring Engine — weighted score 0-100 from detector results + regime."""
from dataclasses import dataclass
from typing import Dict, List, Optional

from strategies.aggressive.detectors.detector_result import DetectorResult
from strategies.aggressive.regime.regime_snapshot import AggressiveRegime, AggressiveRegimeSnapshot


# ── Weights (sum = 1.0) ───────────────────────────────────────────────────────
WEIGHTS: Dict[str, float] = {
    "MomentumBurst":    0.20,
    "VWAPMagnet":       0.15,
    "RibbonRide":       0.15,
    "CompressionBreak": 0.15,
    "VelocitySpike":    0.15,
    "LiquidityVacuum":  0.10,
    "PullbackQuality":  0.10,
}

# ── Regime multipliers ────────────────────────────────────────────────────────
REGIME_MULTIPLIER: Dict[AggressiveRegime, float] = {
    AggressiveRegime.TRENDING_BULL:  1.10,
    AggressiveRegime.TRENDING_BEAR:  1.10,
    AggressiveRegime.WEAK_TREND:     0.90,
    AggressiveRegime.RANGING:        0.80,
    AggressiveRegime.CHOPPY:         0.60,
    AggressiveRegime.HIGH_VOLATILITY:0.75,
    AggressiveRegime.LOW_LIQUIDITY:  0.50,
}

# ── Thresholds ────────────────────────────────────────────────────────────────
REJECT   = 60
WATCH    = 75
GOOD     = 85


@dataclass
class EntryScore:
    score: float                # 0-100
    label: str                  # REJECT | WATCH | GOOD | EXECUTE
    direction: str              # BUY | SELL | NEUTRAL
    confidence: float           # 0-1 weighted avg
    component_scores: Dict[str, float]
    regime_multiplier: float
    raw_score: float            # before regime multiplier


def score_entry(
    results: List[Optional[DetectorResult]],
    regime: AggressiveRegimeSnapshot,
    detector_names: Optional[List[str]] = None,
) -> EntryScore:
    """
    Compute weighted entry score from detector results.

    results  : list of DetectorResult (or None) in same order as detector_names
    regime   : AggressiveRegimeSnapshot
    detector_names: names matching WEIGHTS keys (order must match results)
    """
    if detector_names is None:
        detector_names = list(WEIGHTS.keys())

    raw = 0.0
    total_weight = 0.0
    components: Dict[str, float] = {}
    buy_conf = 0.0
    sell_conf = 0.0

    for name, result in zip(detector_names, results):
        w = WEIGHTS.get(name, 0.0)
        if result is None:
            components[name] = 0.0
            continue
        contrib = result.confidence * result.strength * w * 100
        raw += contrib
        total_weight += w
        components[name] = round(contrib, 2)
        if result.direction == "BUY":
            buy_conf += result.confidence * w
        elif result.direction == "SELL":
            sell_conf += result.confidence * w

    # Normalize to 100 if not all detectors fired
    if total_weight > 0 and total_weight < 1.0:
        raw = raw / total_weight

    # Apply regime multiplier
    mult = REGIME_MULTIPLIER.get(regime.regime, 1.0)
    score = min(raw * mult, 100.0)

    # Direction = dominant side
    direction = "BUY" if buy_conf >= sell_conf else "SELL" if sell_conf > 0 else "NEUTRAL"
    confidence = max(buy_conf, sell_conf)

    # Label
    if score >= GOOD:
        label = "EXECUTE"
    elif score >= WATCH:
        label = "GOOD"
    elif score >= REJECT:
        label = "WATCH"
    else:
        label = "REJECT"

    return EntryScore(
        score=round(score, 2),
        label=label,
        direction=direction,
        confidence=round(confidence, 3),
        component_scores=components,
        regime_multiplier=mult,
        raw_score=round(raw, 2),
    )
