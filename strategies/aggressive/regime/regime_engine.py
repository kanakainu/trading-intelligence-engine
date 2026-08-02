import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

from core.features.feature_models import FeatureSnapshot
from strategies.aggressive.regime.regime_snapshot import AggressiveRegime, AggressiveRegimeSnapshot
from strategies.aggressive.liquidity.liquidity_engine import LiquidityState, LiquiditySnapshot # For type hinting

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
        if len(candles_m5) < 30: # Need enough data for EMAs/ADX
            return self._fallback(features.timestamp)

        metrics = self._compute_metrics(features)
        if not metrics.ema9 or not metrics.ema21 or not metrics.adx: # Ensure critical metrics are present
            return self._fallback(features.timestamp)

        # Evaluate liquidity (need spread, atr, candles_m1, volume_ratio)
        # features.atr is a dict {tf: value}, get M5 or fallback to H1
        atr_dict = features.atr if isinstance(features.atr, dict) else {}
        atr = float(atr_dict.get("M5", atr_dict.get("H1", 0.0))) if atr_dict else 0.0
        
        spread = float(features.spread) if hasattr(features, 'spread') and features.spread is not None else 0.0
        candles_m1 = features.candles.get("M1", [])
        # features.volume_ratio is a dict {tf: value}, get M5 or fallback
        vol_dict = features.volume_ratio if isinstance(features.volume_ratio, dict) else {}
        volume_ratio = float(vol_dict.get("M5", vol_dict.get("H1", 1.0))) if vol_dict else 1.0
        
        # Import here to avoid circular import
        from strategies.aggressive.liquidity.liquidity_engine import evaluate_liquidity
        liq_snap = evaluate_liquidity(
            symbol=features.symbol,
            spread=spread,
            atr=atr,
            candles_m1=candles_m1,
            volume_ratio=volume_ratio
        )

        regime = self._classify_regime(metrics, liq_snap)
        confidence = self._confidence(metrics, regime)

        return AggressiveRegimeSnapshot(
            regime=regime,
            trend_score=min(metrics.adx / 50.0, 1.0), # Normalize ADX for score
            volatility_score=0.5, # Simplified for C7
            liquidity_score=liq_snap.score / 100.0,  # Normalize 0-1
            confidence=confidence,
            timestamp=features.timestamp,
        )

    def _compute_metrics(self, features: FeatureSnapshot) -> M5RegimeMetrics:
        candles = features.candles.get("M5", [])
        closes = [float(c["close"]) for c in candles]
        ema9   = self._ema(closes, 9)
        ema21  = self._ema(closes, 21)
        # slope = last 3 EMA9 values diff
        ema9_series = [self._ema(closes[:i], 9) for i in range(len(closes)-2, len(closes)+1)]
        slope = (ema9_series[-1] - ema9_series[0]) / 2 if len(ema9_series) == 3 else 0.0
        adx   = self._calc_adx(candles)
        return M5RegimeMetrics(ema9=ema9, ema21=ema21, ema_slope=slope, adx=adx)

    @staticmethod
    def _ema(closes: list, period: int) -> float:
        if len(closes) < period:
            return 0.0
        k = 2 / (period + 1)
        val = sum(closes[:period]) / period
        for c in closes[period:]:
            val = c * k + val * (1 - k)
        return val

    @staticmethod
    def _calc_adx(candles: list, period: int = 14) -> float:
        """Simplified ADX from M5 candles (Wilder's smoothing, period=14)."""
        if len(candles) < period + 1:
            return 0.0
        try:
            def _k(c, k): return float(c.get(k) or c.get(k.capitalize()) or c.get(k.upper()) or 0)
            highs  = [_k(c,"high")  for c in candles]
            lows   = [_k(c,"low")   for c in candles]
            closes = [_k(c,"close") for c in candles]
            trs, pdms, mdms = [], [], []
            for i in range(1, len(candles)):
                tr  = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
                pdm = max(highs[i]-highs[i-1], 0) if (highs[i]-highs[i-1]) > (lows[i-1]-lows[i]) else 0
                mdm = max(lows[i-1]-lows[i], 0) if (lows[i-1]-lows[i]) > (highs[i]-highs[i-1]) else 0
                trs.append(tr); pdms.append(pdm); mdms.append(mdm)
            def smooth(vals):
                s = sum(vals[:period])
                result = [s]
                for v in vals[period:]:
                    s = s - s/period + v
                    result.append(s)
                return result
            str_ = smooth(trs); spdm = smooth(pdms); smdm = smooth(mdms)
            dxs = []
            for atr, sp, sm in zip(str_, spdm, smdm):
                if atr == 0: continue
                pdi = 100*sp/atr; mdi = 100*sm/atr
                dx  = 100*abs(pdi-mdi)/(pdi+mdi) if (pdi+mdi) > 0 else 0
                dxs.append(dx)
            return sum(dxs[-period:]) / period if len(dxs) >= period else 0.0
        except Exception:
            return 0.0

    def _classify_regime(self, metrics: M5RegimeMetrics, liq_snap: LiquiditySnapshot) -> AggressiveRegime:
        if liq_snap.state == LiquidityState.LOW_LIQUIDITY:
            return AggressiveRegime.LOW_LIQUIDITY
        if metrics.ema9 > metrics.ema21 and metrics.ema_slope > 0.05:
            return AggressiveRegime.BULL
        elif metrics.ema9 < metrics.ema21 and metrics.ema_slope < -0.05:
            return AggressiveRegime.BEAR
        elif metrics.adx < 15:
            return AggressiveRegime.CHOPPY
        elif 20 <= metrics.adx <= 25:
            return AggressiveRegime.MINOR_TREND
        else:
            return AggressiveRegime.FLAT

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
    from strategies.aggressive.liquidity.liquidity_engine import LiquidityState, evaluate_liquidity

    engine = AggressiveRegimeEngine()

    # Scenario 1: Bullish Regime
    mock_features_bull = Mock()
    mock_features_bull.candles = {"M5": [1]*100} # Enough candles
    mock_features_bull.timestamp = datetime.now()
    mock_features_bull.get_ema.side_effect = lambda tf, period: 105.0 if period == 9 else (100.0 if period == 21 else None)
    mock_features_bull.get_ema_slope.side_effect = lambda tf, period: 0.5 if period == 9 else None
    mock_features_bull.get_adx.return_value = 30.0
    mock_features_bull.spread = 0.1 # Example spread
    mock_features_bull.atr = 0.5 # Example ATR
    mock_features_bull.candles.get.return_value = [{'open':1,'high':1.5,'low':0.5,'close':1.2}] * 100 # Mock M1 candles
    mock_features_bull.volume_ratio = 1.0 # Example volume ratio
    mock_features_bull.symbol = "XAUUSD" # Example symbol
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
    mock_features_bear.spread = 0.1
    mock_features_bear.atr = 0.5
    mock_features_bear.candles.get.return_value = [{'open':1,'high':1.5,'low':0.5,'close':0.8}] * 100
    mock_features_bear.volume_ratio = 1.0
    mock_features_bear.symbol = "XAUUSD"
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
    mock_features_minor.spread = 0.1
    mock_features_minor.atr = 0.5
    mock_features_minor.candles.get.return_value = [{'open':1,'high':1.5,'low':0.5,'close':1.0}] * 100
    mock_features_minor.volume_ratio = 1.0
    mock_features_minor.symbol = "XAUUSD"
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
    mock_features_flat.spread = 0.1
    mock_features_flat.atr = 0.5
    mock_features_flat.candles.get.return_value = [{'open':1,'high':1.5,'low':0.5,'close':1.0}] * 100
    mock_features_flat.volume_ratio = 1.0
    mock_features_flat.symbol = "XAUUSD"
    snapshot_flat = engine.classify(mock_features_flat)
    assert snapshot_flat.regime == AggressiveRegime.FLAT
    assert snapshot_flat.confidence > 0
    print("Flat Regime OK")

    # Scenario 5: Insufficient Data
    mock_features_insufficient = Mock()
    mock_features_insufficient.candles = {"M5": [1]*10}
    mock_features_insufficient.timestamp = datetime.datetime.now()
    mock_features_insufficient.spread = 0.1
    mock_features_insufficient.atr = 0.5
    mock_features_insufficient.candles.get.return_value = []
    mock_features_insufficient.volume_ratio = 1.0
    mock_features_insufficient.symbol = "XAUUSD"
    snapshot_insufficient = engine.classify(mock_features_insufficient)
    assert snapshot_insufficient.regime == AggressiveRegime.FLAT
    print("Insufficient Data Fallback OK")

    # Test 6: LOW_LIQUIDITY Regime
    mock_features_low_liq = Mock()
    mock_features_low_liq.candles = {"M5": [1]*100, "M1": []}
    mock_features_low_liq.timestamp = datetime.datetime.now()
    mock_features_low_liq.spread = 1.0 # High spread
    mock_features_low_liq.atr = 0.1 # Low ATR
    mock_features_low_liq.volume_ratio = 0.5 # Low volume
    mock_features_low_liq.symbol = "XAUUSD"
    # Mock all _compute_metrics to return neutral or non-extreme values
    mock_features_low_liq.get_ema.return_value = 100.0
    mock_features_low_liq.get_ema_slope.return_value = 0.0
    mock_features_low_liq.get_adx.return_value = 10.0
    snapshot_low_liq = engine.classify(mock_features_low_liq)
    assert snapshot_low_liq.regime == AggressiveRegime.LOW_LIQUIDITY, f"Expected LOW_LIQUIDITY, got {snapshot_low_liq.regime}"
    print(f"LOW_LIQUIDITY Regime OK: {snapshot_low_liq.regime}")

    # Test 7: CHOPPY Regime
    mock_features_choppy = Mock()
    mock_features_choppy.candles = {"M5": [1]*100, "M1": [{'open':1,'high':1.1,'low':0.9,'close':1.0}] * 100}
    mock_features_choppy.timestamp = datetime.datetime.now()
    mock_features_choppy.spread = 0.1
    mock_features_choppy.atr = 0.5
    mock_features_choppy.volume_ratio = 1.0
    mock_features_choppy.symbol = "XAUUSD"
    mock_features_choppy.get_ema.return_value = 100.0
    mock_features_choppy.get_ema_slope.return_value = 0.0
    mock_features_choppy.get_adx.return_value = 12.0 # ADX for choppy
    snapshot_choppy = engine.classify(mock_features_choppy)
    assert snapshot_choppy.regime == AggressiveRegime.CHOPPY, f"Expected CHOPPY, got {snapshot_choppy.regime}"
    print(f"CHOPPY Regime OK: {snapshot_choppy.regime}")
