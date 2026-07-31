import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

from core.features.feature_models import FeatureSnapshot
from strategies.aggressive.regime.regime_snapshot import AggressiveRegime, AggressiveRegimeSnapshot

logger = logging.getLogger(__name__)

@dataclass
class M5RegimeMetrics:
    ema9: float
    ema21: float
    ema_slope: float # of EMA9
    adx: float

class AggressiveRegimeEngine:
    def classify(self, features: FeatureSnapshot) -> AggressiveRegimeSnapshot:
        candles_m5 = features.candles.get("M5", [])
        if len(candles_m5) < 50: # Need enough data for EMAs/ADX
            return self._fallback(features.timestamp)

        metrics = self._compute_metrics(features)
        if not metrics.ema9 or not metrics.ema21 or not metrics.adx: # Ensure critical metrics are present
            return self._fallback(features.timestamp)

        regime = self._classify_regime(metrics)
        confidence = self._confidence(metrics, regime)

        return AggressiveRegimeSnapshot(
            regime=regime,
            trend_score=min(metrics.adx / 50.0, 1.0), # Normalize ADX for score
            volatility_score=0.5, # Simplified for C7
            liquidity_score=0.5,  # Simplified for C7
            confidence=confidence,
            timestamp=features.timestamp,
        )

    def _compute_metrics(self, features: FeatureSnapshot) -> M5RegimeMetrics:
        ema9 = features.get_ema("M5", 9) or 0.0
        ema21 = features.get_ema("M5", 21) or 0.0
        ema_slope = features.get_ema_slope("M5", 9) or 0.0 # Slope of EMA9
        adx = features.get_adx("M5") or 0.0
        return M5RegimeMetrics(ema9=ema9, ema21=ema21, ema_slope=ema_slope, adx=adx)

    def _classify_regime(self, metrics: M5RegimeMetrics) -> AggressiveRegime:
        if metrics.ema9 > metrics.ema21 and metrics.ema_slope > 0.0:
            return AggressiveRegime.BULL
        elif metrics.ema9 < metrics.ema21 and metrics.ema_slope < 0.0:
            return AggressiveRegime.BEAR
        elif 20 <= metrics.adx <= 25: # ADX 20-25 for Minor Trend
            return AggressiveRegime.MINOR_TREND
        else:
            return AggressiveRegime.FLAT # ADX < 20 or other conditions

    def _confidence(self, metrics: M5RegimeMetrics, regime: AggressiveRegime) -> float:
        score = 50.0
        if regime == AggressiveRegime.BULL and metrics.ema_slope > 0 and metrics.ema9 > metrics.ema21:
            score += metrics.ema_slope * 100 # Reward strong upward slope
            score += (metrics.ema9 - metrics.ema21) * 50 # Reward spread
        elif regime == AggressiveRegime.BEAR and metrics.ema_slope < 0 and metrics.ema9 < metrics.ema21:
            score -= metrics.ema_slope * 100 # Reward strong downward slope
            score += (metrics.ema21 - metrics.ema9) * 50 # Reward spread
        
        score += metrics.adx # ADX contributes directly to confidence
        
        # Clamp score between 0 and 100
        return max(0.0, min(100.0, score))

    def _fallback(self, timestamp: datetime) -> AggressiveRegimeSnapshot:
        logger.warning(f"Insufficient data for M5 regime classification at {timestamp}. Falling back to FLAT.")
        return AggressiveRegimeSnapshot(
            regime=AggressiveRegime.FLAT,
            trend_score=0.0,
            volatility_score=0.0,
            liquidity_score=0.0,
            confidence=0.0,
            timestamp=timestamp,
        )

if __name__ == '__main__':
    # Mock FeatureSnapshot and test
    from unittest.mock import Mock
    from datetime import datetime

    engine = AggressiveRegimeEngine()

    # Scenario 1: Bullish Regime
    mock_features_bull = Mock()
    mock_features_bull.candles = {"M5": [1]*100} # Enough candles
    mock_features_bull.timestamp = datetime.now()
    mock_features_bull.get_ema.side_effect = lambda tf, period: 105.0 if period == 9 else (100.0 if period == 21 else None)
    mock_features_bull.get_ema_slope.side_effect = lambda tf, period: 0.5 if period == 9 else None
    mock_features_bull.get_adx.return_value = 30.0
    snapshot_bull = engine.classify(mock_features_bull)
    assert snapshot_bull.regime == AggressiveRegime.BULL
    assert snapshot_bull.confidence > 50
    print("Bull Regime OK")

    # Scenario 2: Bearish Regime
    mock_features_bear = Mock()
    mock_features_bear.candles = {"M5": [1]*100}
    mock_features_bear.timestamp = datetime.now()
    mock_features_bear.get_ema.side_effect = lambda tf, period: 95.0 if period == 9 else (100.0 if period == 21 else None)
    mock_features_bear.get_ema_slope.side_effect = lambda tf, period: -0.5 if period == 9 else None
    mock_features_bear.get_adx.return_value = 30.0
    snapshot_bear = engine.classify(mock_features_bear)
    assert snapshot_bear.regime == AggressiveRegime.BEAR
    assert snapshot_bear.confidence > 50
    print("Bear Regime OK")

    # Scenario 3: Minor Trend Regime
    mock_features_minor = Mock()
    mock_features_minor.candles = {"M5": [1]*100}
    mock_features_minor.timestamp = datetime.datetime.now()
    mock_features_minor.get_ema.side_effect = lambda tf, period: 100.0 # EMAs flat
    mock_features_minor.get_ema_slope.side_effect = lambda tf, period: 0.0 # Slope flat
    mock_features_minor.get_adx.return_value = 22.0 # ADX for minor trend
    snapshot_minor = engine.classify(mock_features_minor)
    assert snapshot_minor.regime == AggressiveRegime.MINOR_TREND
    assert snapshot_minor.confidence > 0
    print("Minor Trend Regime OK")

    # Scenario 4: Flat Regime
    mock_features_flat = Mock()
    mock_features_flat.candles = {"M5": [1]*100}
    mock_features_flat.timestamp = datetime.datetime.now()
    mock_features_flat.get_ema.side_effect = lambda tf, period: 100.0 # EMAs flat
    mock_features_flat.get_ema_slope.side_effect = lambda tf, period: 0.0 # Slope flat
    mock_features_flat.get_adx.return_value = 15.0 # ADX for flat
    snapshot_flat = engine.classify(mock_features_flat)
    assert snapshot_flat.regime == AggressiveRegime.FLAT
    assert snapshot_flat.confidence > 0
    print("Flat Regime OK")

    # Scenario 5: Insufficient Data
    mock_features_insufficient = Mock()
    mock_features_insufficient.candles = {"M5": [1]*10}
    mock_features_insufficient.timestamp = datetime.datetime.now()
    snapshot_insufficient = engine.classify(mock_features_insufficient)
    assert snapshot_insufficient.regime == AggressiveRegime.FLAT
    print("Insufficient Data Fallback OK")
