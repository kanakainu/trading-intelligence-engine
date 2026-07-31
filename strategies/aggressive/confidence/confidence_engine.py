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
from strategies.aggressive.opportunity.opportunity_engine import OpportunitySnapshot


@dataclass
class ConfidenceScore:
    """Meta-validation of setup quality."""
    confidence: float           # 0-100
    regime_quality: float       # 0-100
    detector_agreement: float   # 0-100
    liquidity_quality: float    # 0-100
    momentum_quality: float     # 0-100
    opportunity_quality: float  # 0-100 (new)
    historical_success: float   # 0-100 (placeholder)
    verdict: str                # REJECT | WATCH | GOOD | EXCELLENT


def compute_confidence(
    results: List[Optional[DetectorResult]],
    regime: AggressiveRegimeSnapshot,
    liquidity: Optional[LiquiditySnapshot] = None,
    pulse: Optional[PulseSnapshot] = None,
    session: Optional[SessionSnapshot] = None,
    opportunity: Optional[OpportunitySnapshot] = None,
) -> ConfidenceScore:
    """Compute meta-confidence from regime + detectors + liquidity + pulse + session + opportunity."""

    # 0. Session gate
    if session is not None and not session.allowed:
        return ConfidenceScore(
            confidence=0.0, regime_quality=0.0, detector_agreement=0.0,
            liquidity_quality=0.0, momentum_quality=0.0, historical_success=0.0,
            verdict="REJECT", opportunity_quality=0.0
        )

    # 1. Regime quality (updated to map old to new states)
    regime_map = {
        AggressiveRegime.BULL:  90,
        AggressiveRegime.BEAR:  90,
        AggressiveRegime.MINOR_TREND: 60,
        AggressiveRegime.FLAT:        40,
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
                opportunity_quality=0.0
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

    # 5. Opportunity quality (new)
    opportunity_quality = opportunity.score if opportunity else 0.0

    # 6. Historical (placeholder)
    historical_success = 0.0

    weights = {"regime": 0.20, "detector": 0.25, "liquidity": 0.15,
               "momentum": 0.15, "opportunity": 0.15, "historical": 0.10}
    confidence = (
        regime_quality    * weights["regime"]
        + detector_agreement * weights["detector"]
        + liquidity_quality  * weights["liquidity"]
        + momentum_quality   * weights["momentum"]
        + opportunity_quality * weights["opportunity"]
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
        opportunity_quality=round(opportunity_quality, 2),
        historical_success=round(historical_success, 2),
        verdict=verdict,
    )
