"""MomentumBurst — detects explosive M5 momentum spike."""
from typing import Optional
from strategies.aggressive.detectors.base_detector import BaseDetector
from strategies.aggressive.detectors.detector_result import DetectorResult
from core.features.feature_models import FeatureSnapshot
from strategies.aggressive.regime.regime_snapshot import AggressiveRegimeSnapshot, AggressiveRegime


class MomentumBurst(BaseDetector):
    @property
    def name(self) -> str:
        return "MomentumBurst"

    def detect(
        self, features: FeatureSnapshot, regime: AggressiveRegimeSnapshot
    ) -> Optional[DetectorResult]:
        candles = features.candles.get("M5", [])
        if len(candles) < 5:
            return None

        # Block low liquidity or choppy
        if regime.regime in (AggressiveRegime.LOW_LIQUIDITY, AggressiveRegime.CHOPPY):
            return None

        last = candles[-1]
        body = abs(last["close"] - last["open"])
        wick_up = last["high"] - max(last["open"], last["close"])
        wick_down = min(last["open"], last["close"]) - last["low"]
        total_range = last["high"] - last["low"]

        # Momentum burst = body > 70% of range + volume spike
        body_ratio = body / total_range if total_range else 0
        volume_ratio = features.volume_ratio.get("M5", 1.0)

        if body_ratio < 0.7 or volume_ratio < 1.3:
            return None

        direction = "BUY" if last["close"] > last["open"] else "SELL"
        confidence = min(body_ratio + (volume_ratio - 1.0), 1.0)
        strength = body_ratio

        return DetectorResult(
            direction=direction,
            confidence=confidence,
            strength=strength,
            reason=f"M5 momentum burst body={body_ratio:.2f} vol={volume_ratio:.2f}",
            metadata={"body_ratio": body_ratio, "volume_ratio": volume_ratio},
        )
