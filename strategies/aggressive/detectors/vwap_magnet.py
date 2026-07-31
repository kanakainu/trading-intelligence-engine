"""VWAPMagnet — price approaching VWAP with compression."""
from typing import Optional
from strategies.aggressive.detectors.base_detector import BaseDetector
from strategies.aggressive.detectors.detector_result import DetectorResult
from core.features.feature_models import FeatureSnapshot
from strategies.aggressive.regime.regime_snapshot import AggressiveRegimeSnapshot, AggressiveRegime


class VWAPMagnet(BaseDetector):
    @property
    def name(self) -> str:
        return "VWAPMagnet"

    def detect(
        self, features: FeatureSnapshot, regime: AggressiveRegimeSnapshot
    ) -> Optional[DetectorResult]:
        candles = features.candles.get("M5", [])
        if len(candles) < 10:
            return None

        if regime.regime == AggressiveRegime.LOW_LIQUIDITY:
            return None

        vwap = features.get_vwap("M5")
        if not vwap:
            return None

        last = candles[-1]
        price = last["close"]
        dist = abs(price - vwap) / vwap if vwap else 1.0

        # Near VWAP (< 0.3% distance)
        if dist > 0.003:
            return None

        # Check ATR compression
        atr = features.get_atr("M5") or 0
        atr_pct = features.atr_percent.get("M5", 0.01)
        if atr_pct > 0.015:  # Too volatile
            return None

        direction = "BUY" if price < vwap else "SELL"
        confidence = 1.0 - (dist / 0.003)  # closer = higher conf
        strength = regime.trend_score

        return DetectorResult(
            direction=direction,
            confidence=confidence,
            strength=strength,
            reason=f"VWAP magnet dist={dist*100:.2f}% atr_pct={atr_pct*100:.2f}%",
            metadata={"vwap": vwap, "price": price, "distance_pct": dist * 100},
        )
