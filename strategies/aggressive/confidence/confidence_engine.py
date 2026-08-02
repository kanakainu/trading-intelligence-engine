"""Confidence Engine — REFACTORED v2.

Confidence = ranking only, NOT a gate.
Evaluates ONLY: detector agreement, regime fit, momentum quality, historical reliability.

NO session/opportunity/liquidity weights (those are gates, not confidence factors).
"""
from dataclasses import dataclass
from typing import List, Optional

from strategies.aggressive.detectors.detector_result import DetectorResult
from strategies.aggressive.regime.regime_snapshot import AggressiveRegime, AggressiveRegimeSnapshot
from strategies.aggressive.liquidity.liquidity_engine import LiquiditySnapshot, LiquidityState
from strategies.aggressive.market_pulse.market_pulse import PulseSnapshot
from strategies.aggressive.session.session_profile import SessionSnapshot
from strategies.aggressive.opportunity.opportunity_engine import OpportunitySnapshot
from strategies.aggressive.confidence.episode_store import success_rate as _episode_success_rate


@dataclass
class ConfidenceScore:
    """Meta-validation of setup quality."""
    confidence: float           # 0-100
    regime_quality: float       # 0-100
    detector_agreement: float   # 0-100
    momentum_quality: float     # 0-100
    historical_success: float   # 0-100
    verdict: str                # REJECT | WATCH | GOOD | EXCELLENT


def compute_confidence(
    results: List[Optional[DetectorResult]],
    regime: AggressiveRegimeSnapshot,
    liquidity: Optional[LiquiditySnapshot] = None,
    pulse: Optional[PulseSnapshot] = None,
    session: Optional[SessionSnapshot] = None,
    opportunity: Optional[OpportunitySnapshot] = None,
    symbol: str = "",
    setup_name: str = "",
) -> ConfidenceScore:
    """Compute meta-confidence from regime + detectors + momentum + history.

    REFACTORED: No session/opportunity/liquidity weights (those are gates).
    Confidence = ranking only, NOT a gate.
    """

    # 0. Session gate (early exit)
    if session is not None and not session.allowed:
        return ConfidenceScore(
            confidence=0.0,
            regime_quality=0.0,
            detector_agreement=0.0,
            momentum_quality=0.0,
            historical_success=0.0,
            verdict="REJECT"
        )

    # 1. Regime quality
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

    # 3. Momentum quality
    if pulse is not None:
        momentum_quality = pulse.pulse
    elif valid:
        momentum_quality = (sum(r.strength for r in valid) / len(valid)) * 100
    else:
        momentum_quality = 0.0

    # 4. Historical success — Episode Memory (sqlite3)
    historical_success = _episode_success_rate(symbol, setup_name) if symbol and setup_name else 50.0

    # 5. Weights and aggregation (REFACTORED — no session/opportunity/liquidity)
    # Confidence = ranking only, NOT a gate
    weights = {
        "regime": 0.30,
        "detector": 0.40,
        "momentum": 0.20,
        "historical": 0.10,
    }

    confidence = (
        regime_quality * weights["regime"]
        + detector_agreement * weights["detector"]
        + momentum_quality * weights["momentum"]
        + historical_success * weights["historical"]
    )

    # Verdict thresholds (lowered to 55 for GOOD)
    if confidence >= 80:
        verdict = "EXCELLENT"
    elif confidence >= 55:
        verdict = "GOOD"
    elif confidence >= 40:
        verdict = "WATCH"
    else:
        verdict = "REJECT"

    return ConfidenceScore(
        confidence=round(confidence, 2),
        regime_quality=round(regime_quality, 2),
        detector_agreement=round(detector_agreement, 2),
        momentum_quality=round(momentum_quality, 2),
        historical_success=round(historical_success, 2),
        verdict=verdict,
    )
