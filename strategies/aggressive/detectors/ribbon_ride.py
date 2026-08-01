"""RibbonRide — EMA ribbon alignment + trend follow."""
from typing import Optional
from strategies.aggressive.detectors.base_detector import BaseDetector
from strategies.aggressive.detectors.detector_result import DetectorResult
from core.features.feature_models import FeatureSnapshot
from strategies.aggressive.regime.regime_snapshot import AggressiveRegimeSnapshot, AggressiveRegime


class RibbonRide(BaseDetector):
    @property
    def name(self) -> str:
        return "RibbonRide"

    def detect(
        self, features: FeatureSnapshot, regime: AggressiveRegimeSnapshot
    ) -> Optional[DetectorResult]:
        if regime.regime not in (AggressiveRegime.BULL, AggressiveRegime.BEAR):
            return None

        ema20 = features.get_ema("M5", 20)
        ema50 = features.get_ema("M5", 50)
        if not (ema20 and ema50):
            return None

        # Ribbon aligned = EMA20 > EMA50 (bull) or EMA20 < EMA50 (bear)
        if regime.regime == AggressiveRegime.BULL:
            if ema20 <= ema50:
                return None
            direction = "BUY"
        else:
            if ema20 >= ema50:
                return None
            direction = "SELL"

        spread = abs(ema20 - ema50) / ema50 if ema50 else 0
        confidence = min(spread * 50, 0.9)  # normalize
        strength = regime.trend_score

        return DetectorResult(
            direction=direction,
            confidence=confidence,
            strength=strength,
            reason=f"EMA ribbon aligned ema20={ema20:.2f} ema50={ema50:.2f}",
            metadata={"ema20": ema20, "ema50": ema50, "spread_pct": spread * 100},
        )
