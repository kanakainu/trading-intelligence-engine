"""Confidence Engine — meta-layer validating setup quality before entry scoring.

Inputs: Regime, Detector Agreement, Liquidity, Momentum Quality, Historical Success Rate
Output: Confidence Score (0-100) → gates Entry Scoring Engine
"""
from dataclasses import dataclass
from typing import List, Optional

from strategies.aggressive.detectors.detector_result import DetectorResult
from strategies.aggressive.regime.regime_snapshot import AggressiveRegime, AggressiveRegimeSnapshot


@dataclass
class ConfidenceScore:
    """Meta-validation of setup quality."""
    confidence: float           # 0-100
    regime_quality: float       # 0-100
    detector_agreement: float   # 0-100
    liquidity_quality: float    # 0-100
    momentum_quality: float     # 0-100
    historical_success: float   # 0-100 (placeholder — needs actual backtest data)
    verdict: str                # REJECT | WATCH | GOOD | EXCELLENT


def compute_confidence(
    results: List[Optional[DetectorResult]],
    regime: AggressiveRegimeSnapshot,
) -> ConfidenceScore:
    """
    Compute meta-confidence from regime + detector agreement + liquidity + momentum.

    Historical success rate = placeholder (0.0) until backtest integration.
    """
    # 1. Regime Quality (0-100)
    regime_map = {
        AggressiveRegime.TRENDING_BULL:  90,
        AggressiveRegime.TRENDING_BEAR:  90,
        AggressiveRegime.WEAK_TREND:     60,
        AggressiveRegime.RANGING:        40,
        AggressiveRegime.CHOPPY:         20,
        AggressiveRegime.HIGH_VOLATILITY:50,
        AggressiveRegime.LOW_LIQUIDITY:  10,
    }
    regime_quality = regime_map.get(regime.regime, 50)

    # 2. Detector Agreement (0-100)
    valid = [r for r in results if r is not None]
    if not valid:
        detector_agreement = 0.0
    else:
        buy = sum(1 for r in valid if r.direction == "BUY")
        sell = sum(1 for r in valid if r.direction == "SELL")
        total = len(valid)
        dominant = max(buy, sell)
        # Agreement = (dominant detectors / total) * 100
        detector_agreement = (dominant / total) * 100 if total else 0

    # 3. Liquidity Quality (0-100)
    liq = regime.liquidity_score
    liquidity_quality = min(liq * 100, 100)

    # 4. Momentum Quality (0-100)
    # Proxy: average strength from fired detectors
    if not valid:
        momentum_quality = 0.0
    else:
        avg_strength = sum(r.strength for r in valid) / len(valid)
        momentum_quality = avg_strength * 100

    # 5. Historical Success Rate (0-100)
    # Placeholder — needs actual backtest/learning data
    historical_success = 0.0  # TODO: integrate with LearningEngine

    # Aggregate confidence (weighted avg)
    weights = {
        "regime": 0.25,
        "detector": 0.30,
        "liquidity": 0.20,
        "momentum": 0.20,
        "historical": 0.05,  # low weight until backtest ready
    }
    confidence = (
        regime_quality * weights["regime"]
        + detector_agreement * weights["detector"]
        + liquidity_quality * weights["liquidity"]
        + momentum_quality * weights["momentum"]
        + historical_success * weights["historical"]
    )

    # Verdict
    if confidence >= 80:
        verdict = "EXCELLENT"
    elif confidence >= 65:
        verdict = "GOOD"
    elif confidence >= 50:
        verdict = "WATCH"
    else:
        verdict = "REJECT"

    return ConfidenceScore(
        confidence=round(confidence, 2),
        regime_quality=round(regime_quality, 2),
        detector_agreement=round(detector_agreement, 2),
        liquidity_quality=round(liquidity_quality, 2),
        momentum_quality=round(momentum_quality, 2),
        historical_success=round(historical_success, 2),
        verdict=verdict,
    )
