"""VelocitySpike — rapid price movement in 3-5 candles."""
from typing import Optional
from strategies.aggressive.detectors.base_detector import BaseDetector
from strategies.aggressive.detectors.detector_result import DetectorResult
from core.features.feature_models import FeatureSnapshot
from strategies.aggressive.regime.regime_snapshot import AggressiveRegimeSnapshot, AggressiveRegime


class VelocitySpike(BaseDetector):
    @property
    def name(self) -> str:
        return "VelocitySpike"

    def detect(
        self, features: FeatureSnapshot, regime: AggressiveRegimeSnapshot
    ) -> Optional[DetectorResult]:
        candles = features.candles.get("M5", [])
        if len(candles) < 5:
            return None

        if regime.regime in (AggressiveRegime.LOW_LIQUIDITY, AggressiveRegime.CHOPPY):
            return None

        # Velocity = sum of last 3 candles' close change
        velocity = sum(
            candles[i]["close"] - candles[i - 1]["close"] for i in range(-3, 0)
        )
        atr = features.get_atr("M5") or 1.0

        # Velocity spike = movement > 2x ATR in 3 candles
        if abs(velocity) < atr * 2:
            return None

        direction = "BUY" if velocity > 0 else "SELL"
        confidence = min(abs(velocity) / (atr * 3), 0.95)
        strength = abs(velocity) / atr / 2  # normalize

        return DetectorResult(
            direction=direction,
            confidence=confidence,
            strength=strength,
            reason=f"Velocity spike vel={velocity:.2f} atr={atr:.2f}",
            metadata={"velocity": velocity, "atr": atr, "velocity_atr_ratio": velocity / atr},
        )
