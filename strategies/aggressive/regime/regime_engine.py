"""Aggressive Regime Engine — M5 scalping regime classifier."""
from datetime import datetime
from typing import Dict, List

from core.features.feature_models import FeatureSnapshot
from strategies.aggressive.regime.regime_snapshot import AggressiveRegime, AggressiveRegimeSnapshot
from strategies.aggressive.regime import regime_rules as rules


class AggressiveRegimeEngine:
    """Classify market regime for aggressive scalping strategy."""

    def classify(self, features: FeatureSnapshot) -> AggressiveRegimeSnapshot:
        """Classify regime from M5 candles + FeatureSnapshot."""
        candles = features.candles.get("M5", [])
        if len(candles) < 50:
            return self._fallback(features.timestamp)

        # Compute metrics
        adx = self._adx_proxy(features)
        ema_slope = self._ema_slope(features)
        atr_pct = features.atr_percent.get("M5", 0.0)
        volume_ratio = features.volume_ratio.get("M5", 1.0)

        # Score components
        trend_score = min(adx / rules.STRONG_TREND_ADX, 1.0)
        volatility_score = min(atr_pct / rules.HIGH_VOLATILITY_ATR_PCT, 1.0)
        liquidity_score = volume_ratio

        # Classify regime
        regime = self._classify_regime(adx, ema_slope, atr_pct, volume_ratio)
        confidence = self._confidence(trend_score, volatility_score, liquidity_score)

        return AggressiveRegimeSnapshot(
            regime=regime,
            trend_score=trend_score,
            volatility_score=volatility_score,
            liquidity_score=liquidity_score,
            confidence=confidence,
            timestamp=features.timestamp,
        )

    def _adx_proxy(self, features: FeatureSnapshot) -> float:
        """ADX14 proxy from EMA slope + ATR."""
        ema20 = features.get_ema("M5", 20) or 0
        ema50 = features.get_ema("M5", 50) or 0
        atr = features.get_atr("M5") or 0
        if not (ema20 and ema50 and atr):
            return 0.0
        spread = abs(ema20 - ema50)
        return min((spread / atr) * 10, 100)

    def _ema_slope(self, features: FeatureSnapshot) -> float:
        """EMA50 slope (change per period)."""
        return features.get_ema_slope("M5", 50) or 0.0

    def _classify_regime(
        self, adx: float, ema_slope: float, atr_pct: float, volume_ratio: float
    ) -> AggressiveRegime:
        """Classify regime from metrics."""
        if volume_ratio < rules.LOW_LIQUIDITY_VOLUME_RATIO:
            return AggressiveRegime.LOW_LIQUIDITY
        if atr_pct > rules.HIGH_VOLATILITY_ATR_PCT:
            return AggressiveRegime.HIGH_VOLATILITY
        if adx < rules.RANGING_ADX:
            return AggressiveRegime.RANGING if atr_pct < 0.01 else AggressiveRegime.CHOPPY
        if adx < rules.WEAK_TREND_ADX:
            return AggressiveRegime.WEAK_TREND

        # Strong trend — check direction
        if abs(ema_slope) < rules.STRONG_SLOPE_THRESHOLD:
            return AggressiveRegime.WEAK_TREND
        return AggressiveRegime.TRENDING_BULL if ema_slope > 0 else AggressiveRegime.TRENDING_BEAR

    def _confidence(self, trend: float, vol: float, liq: float) -> float:
        """Aggregate confidence from component scores."""
        return (trend * 0.5 + vol * 0.3 + liq * 0.2)

    def _fallback(self, timestamp: datetime) -> AggressiveRegimeSnapshot:
        """Fallback when insufficient data."""
        return AggressiveRegimeSnapshot(
            regime=AggressiveRegime.RANGING,
            trend_score=0.0,
            volatility_score=0.0,
            liquidity_score=0.0,
            confidence=0.0,
            timestamp=timestamp,
        )
