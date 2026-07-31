"""Confidence Engine — meta-layer validating setup quality before entry scoring.

Inputs: Regime, Detector Agreement, Liquidity, Momentum Quality, Historical Success Rate
Output: Confidence Score (0-100) → gates Entry Scoring Engine
"""
from dataclasses import dataclass
from typing import List, Optional

from strategies.aggressive.detectors.detector_result import DetectorResult
from strategies.aggressive.regime.regime_snapshot import AggressiveRegime, AggressiveRegimeSnapshot
from strategies.aggressive.liquidity.liquidity_engine import LiquiditySnapshot, LiquidityState
from strategies.aggressive.market_pulse.market_pulse import PulseSnapshot
from strategies.aggressive.session.session_profile import SessionSnapshot


@dataclass
class ConfidenceScore:
    """Meta-validation of setup quality."""
    confidence: float           # 0-100
    regime_quality: float       # 0-100
    detector_agreement: float   # 0-100
    liquidity_quality: float    # 0-100
    momentum_quality: float     # 0-100
    historical_success: float   # 0-100 (placeholder)
    verdict: str                # REJECT | WATCH | GOOD | EXCELLENT


def compute_confidence(
    results: List[Optional[DetectorResult]],
    regime: AggressiveRegimeSnapshot,
    liquidity: Optional[LiquiditySnapshot] = None,
    pulse: Optional[PulseSnapshot] = None,
    session: Optional[SessionSnapshot] = None,
) -> ConfidenceScore:
    """Compute meta-confidence from regime + detectors + liquidity + pulse + session."""

    # 0. Session gate
    if session is not None and not session.allowed:
        return ConfidenceScore(
            confidence=0.0, regime_quality=0.0, detector_agreement=0.0,
            liquidity_quality=0.0, momentum_quality=0.0, historical_success=0.0,
            verdict="REJECT",
        )

    # 1. Regime quality
    regime_map = {
        AggressiveRegime.TRENDING_BULL:  90,
        AggressiveRegime.TRENDING_BEAR:  90,
        AggressiveRegime.WEAK_TREND:     60,
        AggressiveRegime.RANGING:        40,
        AggressiveRegime.CHOPPY:         20,
        AggressiveRegime.HIGH_VOLATILITY:50,
        AggressiveRegime.LOW_LIQUIDITY:  10,
    }
    regime_quality = float(regime_map.get(regime.regime, 50))

    # 2. Detector agreement
    valid = [r for r in results if r is not None]
    if not valid:
        detector_agreement = 0.0
    else:
        buy = sum(1 for r in valid if r.direction == "BUY")
        sell = sum(1 for r in valid if r.direction == "SELL")
        dominant = max(buy, sell)
        detector_agreement = (dominant / len(valid)) * 100

    # 3. Liquidity quality — use LiquiditySnapshot.score if available
    if liquidity is not None:
        if liquidity.state == LiquidityState.TOXIC:
            return ConfidenceScore(
                confidence=0.0, regime_quality=regime_quality,
                detector_agreement=detector_agreement, liquidity_quality=0.0,
                momentum_quality=0.0, historical_success=0.0, verdict="REJECT",
            )
        liquidity_quality = liquidity.score
    else:
        liquidity_quality = min(regime.liquidity_score * 100, 100.0)

    # 4. Momentum quality — use MarketPulse.pulse if available
    if pulse is not None:
        momentum_quality = pulse.pulse
    elif valid:
        momentum_quality = (sum(r.strength for r in valid) / len(valid)) * 100
    else:
        momentum_quality = 0.0

    # 5. Historical (placeholder)
    historical_success = 0.0

    weights = {"regime": 0.25, "detector": 0.30, "liquidity": 0.20,
               "momentum": 0.20, "historical": 0.05}
    confidence = (
        regime_quality    * weights["regime"]
        + detector_agreement * weights["detector"]
        + liquidity_quality  * weights["liquidity"]
        + momentum_quality   * weights["momentum"]
        + historical_success * weights["historical"]
    )

    # Session score multiplier
    if session is not None:
        confidence *= (session.score / 100.0)

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
