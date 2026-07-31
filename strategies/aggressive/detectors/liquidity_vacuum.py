"""LiquidityVacuum — detect liquidity drop + snap-back potential."""
from typing import Optional
from strategies.aggressive.detectors.base_detector import BaseDetector
from strategies.aggressive.detectors.detector_result import DetectorResult
from core.features.feature_models import FeatureSnapshot
from strategies.aggressive.regime.regime_snapshot import AggressiveRegimeSnapshot, AggressiveRegime


class LiquidityVacuum(BaseDetector):
    @property
    def name(self) -> str:
        return "LiquidityVacuum"

    def detect(
        self, features: FeatureSnapshot, regime: AggressiveRegimeSnapshot
    ) -> Optional[DetectorResult]:
        candles = features.candles.get("M5", [])
        if len(candles) < 10:
            return None

        volume_ratio = features.volume_ratio.get("M5", 1.0)

        # Liquidity vacuum = volume drop < 0.6 of MA
        if volume_ratio > 0.6:
            return None

        # Price near swing level (support/resistance)
        support = features.get_nearest_support("M5")
        resistance = features.get_nearest_resistance("M5")
        last = candles[-1]
        price = last["close"]

        near_support = support and abs(price - support) / price < 0.003
        near_resistance = resistance and abs(price - resistance) / price < 0.003

        if not (near_support or near_resistance):
            return None

        direction = "BUY" if near_support else "SELL"
        confidence = (1.0 - volume_ratio) * 0.8  # low volume = higher conf
        strength = 0.7  # moderate

        return DetectorResult(
            direction=direction,
            confidence=confidence,
            strength=strength,
            reason=f"Liquidity vacuum vol_ratio={volume_ratio:.2f} near_{'support' if near_support else 'resistance'}",
            metadata={
                "volume_ratio": volume_ratio,
                "support": support,
                "resistance": resistance,
                "price": price,
            },
        )
