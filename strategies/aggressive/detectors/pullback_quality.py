"""PullbackQuality — clean pullback after trend move."""
from typing import Optional
from strategies.aggressive.detectors.base_detector import BaseDetector
from strategies.aggressive.detectors.detector_result import DetectorResult
from core.features.feature_models import FeatureSnapshot
from strategies.aggressive.regime.regime_snapshot import AggressiveRegimeSnapshot, AggressiveRegime


class PullbackQuality(BaseDetector):
    @property
    def name(self) -> str:
        return "PullbackQuality"

    def detect(
        self, features: FeatureSnapshot, regime: AggressiveRegimeSnapshot
    ) -> Optional[DetectorResult]:
        candles = features.candles.get("M5", [])
        if len(candles) < 10:
            return None

        if regime.regime not in (AggressiveRegime.TRENDING_BULL, AggressiveRegime.TRENDING_BEAR):
            return None

        ema20 = features.get_ema("M5", 20)
        if not ema20:
            return None

        last = candles[-1]
        price = last["close"]

        # Pullback = price near EMA20 (within 0.5%)
        dist = abs(price - ema20) / ema20 if ema20 else 1.0
        if dist > 0.005:
            return None

        # Check last 3 candles = pullback (opposite of trend)
        if regime.regime == AggressiveRegime.TRENDING_BULL:
            pullback = all(candles[i]["close"] < candles[i - 1]["close"] for i in range(-3, 0))
            if not pullback:
                return None
            direction = "BUY"
        else:
            pullback = all(candles[i]["close"] > candles[i - 1]["close"] for i in range(-3, 0))
            if not pullback:
                return None
            direction = "SELL"

        confidence = 1.0 - (dist / 0.005)
        strength = regime.trend_score

        return DetectorResult(
            direction=direction,
            confidence=confidence,
            strength=strength,
            reason=f"Quality pullback to EMA20 dist={dist*100:.2f}%",
            metadata={"ema20": ema20, "price": price, "distance_pct": dist * 100},
        )
