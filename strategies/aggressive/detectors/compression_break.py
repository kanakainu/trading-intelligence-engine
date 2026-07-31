"""CompressionBreak — tight ATR then breakout."""
from typing import Optional
from strategies.aggressive.detectors.base_detector import BaseDetector
from strategies.aggressive.detectors.detector_result import DetectorResult
from core.features.feature_models import FeatureSnapshot
from strategies.aggressive.regime.regime_snapshot import AggressiveRegimeSnapshot, AggressiveRegime


class CompressionBreak(BaseDetector):
    @property
    def name(self) -> str:
        return "CompressionBreak"

    def detect(
        self, features: FeatureSnapshot, regime: AggressiveRegimeSnapshot
    ) -> Optional[DetectorResult]:
        candles = features.candles.get("M5", [])
        if len(candles) < 20:
            return None

        if regime.regime == AggressiveRegime.LOW_LIQUIDITY:
            return None

        atr = features.get_atr("M5") or 0
        atr_pct = features.atr_percent.get("M5", 0.01)

        # Low ATR (compression) = < 0.6%
        if atr_pct > 0.006:
            return None

        last = candles[-1]
        prev = candles[-2]
        body = abs(last["close"] - last["open"])
        prev_body = abs(prev["close"] - prev["open"])

        # Breakout = current body > 2x prev body
        if body < prev_body * 2:
            return None

        direction = "BUY" if last["close"] > last["open"] else "SELL"
        confidence = min(body / prev_body / 3.0, 0.95)
        strength = body / (last["high"] - last["low"]) if (last["high"] - last["low"]) else 0

        return DetectorResult(
            direction=direction,
            confidence=confidence,
            strength=strength,
            reason=f"Compression break atr_pct={atr_pct*100:.2f}% body_ratio={body/prev_body:.2f}x",
            metadata={"atr_pct": atr_pct * 100, "body_expansion": body / prev_body},
        )
