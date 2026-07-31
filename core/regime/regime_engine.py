"""Regime Engine — Classifies market regime from FeatureSnapshot inputs.

Pure classification — NO strategy logic.
Reusable by any strategy/detector.
"""
from typing import Dict, Optional
from core.regime.regime_models import (
    Regime, TrendDirection, RegimeSnapshot, RegimeInputs
)


class RegimeEngine:
    """
    Market regime classifier using multi-factor analysis.

    Factors (weighted):
    1. ADX (trend strength) — 30%
    2. EMA Slope Alignment — 25%
    3. ATR Expansion (volatility regime) — 20%
    4. VWAP Distance (mean reversion pressure) — 15%
    5. Volume Participation — 10%

    Outputs: RegimeSnapshot with regime enum + confidence + component scores.
    """

    # Thresholds (tunable)
    ADX_WEAK = 15
    ADX_TREND = 25
    ADX_STRONG = 40
    ADX_EXTREME = 50

    EMA_SLOPE_FLAT = 0.0001
    EMA_SLOPE_TREND = 0.0005
    EMA_SLOPE_STRONG = 0.0015

    ATR_PCT_LOW = 0.003    # 0.3%
    ATR_PCT_NORMAL = 0.008  # 0.8%
    ATR_PCT_HIGH = 0.015   # 1.5%
    ATR_PCT_NEWS = 0.05    # 5%  — special regime threshold (was HIGH*2 = 3%)

    VWAP_DIST_CLOSE = 0.001  # 0.1%
    VWAP_DIST_NORMAL = 0.005  # 0.5%
    VWAP_DIST_FAR = 0.015     # 1.5%

    VOLUME_LOW = 0.5
    VOLUME_NORMAL = 1.0
    VOLUME_HIGH = 2.0

    SPREAD_HIGH_PCT = 0.0005  # 0.05% of price
    TICK_SPEED_LOW = 0.5

    def __init__(self):
        pass

    def classify(self, inputs: RegimeInputs) -> RegimeSnapshot:
        """Classify regime from inputs."""
        tf = inputs.timeframe

        # Extract values for primary timeframe
        ema = inputs.ema.get(tf, {})
        ema_slope = inputs.ema_slope.get(tf, {})
        atr = inputs.atr.get(tf, 0.0)
        atr_pct = inputs.atr_percent.get(tf, 0.0)
        vwap_dist = inputs.distance_to_vwap.get(tf, 0.0)
        vol_ratio = inputs.volume_ratio.get(tf, 1.0)
        vol_spike = inputs.volume_spike.get(tf, 0.0)
        mom_score = inputs.momentum_score.get(tf, 0.0)
        spread = inputs.spread

        # Get current price for VWAP distance normalization
        price = inputs.current_price

        # Compute component scores (0-1)
        adx_score = self._compute_adx_score(atr_pct, ema)
        ema_slope_score = self._compute_ema_slope_score(ema_slope, ema)
        atr_expansion_score = self._compute_atr_expansion_score(atr_pct, vol_spike)
        vwap_distance_score = self._compute_vwap_distance_score(vwap_dist, price)
        volume_score = self._compute_volume_score(vol_ratio, vol_spike)

        # Detect special regimes first
        regime = self._detect_special_regimes(
            spread=spread,
            atr_pct=atr_pct,
            vol_ratio=vol_ratio,
            tick_speed=inputs.tick_speed,
            vwap_dist=abs(vwap_dist),
        )

        if regime == Regime.UNKNOWN:
            # Normal classification
            regime, trend_dir, confidence = self._classify_normal(
                adx_score=adx_score,
                ema_slope_score=ema_slope_score,
                atr_expansion_score=atr_expansion_score,
                vwap_distance_score=vwap_distance_score,
                volume_score=volume_score,
                mom_score=mom_score,
                ema_slope=ema_slope,
            )
        else:
            trend_dir = TrendDirection.FLAT
            confidence = 0.9  # High confidence for special regimes

        return RegimeSnapshot(
            regime=regime,
            trend_direction=trend_dir,
            confidence=confidence,
            adx_score=adx_score,
            ema_slope_score=ema_slope_score,
            atr_expansion_score=atr_expansion_score,
            vwap_distance_score=vwap_distance_score,
            volume_score=volume_score,
            adx=atr_pct * 100,  # approximate ADX from ATR%
            ema_slope=ema_slope.get(f"ema21_slope", 0.0) or ema_slope.get(f"ema50_slope", 0.0) or 0.0,
            atr_pct=atr_pct,
            vwap_distance=vwap_dist,
            volume_ratio=vol_ratio,
            symbol=inputs.symbol,
            timeframe=inputs.timeframe,
            timestamp=inputs.timestamp or __import__("datetime").datetime.now(),
            scan_id=inputs.scan_id,
        )

    def _detect_special_regimes(
        self,
        spread: float,
        atr_pct: float,
        vol_ratio: float,
        tick_speed: float,
        vwap_dist: float,
    ) -> Regime:
        """Check for NEWS, LOW_LIQUIDITY, EXHAUSTION."""
        # LOW_LIQUIDITY: low volume + low tick speed
        if vol_ratio < self.VOLUME_LOW and tick_speed < self.TICK_SPEED_LOW:
            return Regime.LOW_LIQUIDITY

        # NEWS: extreme ATR expansion + volume spike
        if atr_pct > self.ATR_PCT_NEWS and vol_ratio > self.VOLUME_HIGH:
            return Regime.NEWS

        # EXHAUSTION: extreme VWAP distance + high ATR (normalized by price in caller)
        # vwap_dist here is already percentage (from caller)
        if vwap_dist > self.VWAP_DIST_FAR * 3 and atr_pct > self.ATR_PCT_HIGH:
            return Regime.EXHAUSTION

        return Regime.UNKNOWN

    def _classify_normal(
        self,
        adx_score: float,
        ema_slope_score: float,
        atr_expansion_score: float,
        vwap_distance_score: float,
        volume_score: float,
        mom_score: float,
        ema_slope: Dict[str, float],
    ) -> tuple:
        """Classify normal regimes (RANGE, CHOPPY, EARLY_TREND, TRENDING, STRONG_TREND)."""

        # Weighted composite score
        composite = (
            adx_score * 0.30 +
            ema_slope_score * 0.25 +
            atr_expansion_score * 0.20 +
            vwap_distance_score * 0.15 +
            volume_score * 0.10
        )

        # Determine trend direction from EMA slope
        ema21_slope = ema_slope.get("ema21_slope", 0.0)
        ema50_slope = ema_slope.get("ema50_slope", 0.0)
        avg_slope = (ema21_slope + ema50_slope) / 2 if ema21_slope and ema50_slope else (ema21_slope or ema50_slope or 0.0)

        if avg_slope > self.EMA_SLOPE_TREND:
            trend_dir = TrendDirection.UP
        elif avg_slope < -self.EMA_SLOPE_TREND:
            trend_dir = TrendDirection.DOWN
        else:
            trend_dir = TrendDirection.FLAT

        # Regime thresholds
        if composite < 0.20:  # Lowered from 0.25
            # Low trend strength — check if choppy or range
            if atr_expansion_score >= 0.55:
                regime = Regime.CHOPPY
                confidence = 0.7
            else:
                regime = Regime.RANGE
                confidence = 0.8
        elif composite < 0.45:
            regime = Regime.EARLY_TREND
            confidence = 0.65
        elif composite < 0.70:
            regime = Regime.TRENDING
            confidence = 0.75
        else:
            regime = Regime.STRONG_TREND
            confidence = 0.85

        # Boost confidence if all factors align
        if adx_score > 0.7 and ema_slope_score > 0.7 and volume_score > 0.6:
            confidence = min(confidence + 0.1, 0.95)

        return regime, trend_dir, confidence

    # ===== Component Scorers =====
    def _compute_adx_score(self, atr_pct: float, ema: Dict[str, float]) -> float:
        """
        Approximate ADX from ATR% and EMA separation.
        High ATR% + EMA separation = strong trend.
        High ATR% + NO EMA separation = CHOPPY (not trending).
        """
        # ATR% normalized (0.3% = weak, 1.5% = strong)
        atr_norm = min(atr_pct / self.ATR_PCT_NORMAL, 1.0) if self.ATR_PCT_NORMAL > 0 else 0.5

        # EMA separation: ema8 vs ema21 vs ema50
        ema8 = ema.get("ema8", 0)
        ema21 = ema.get("ema21", 0)
        ema50 = ema.get("ema50", 0)
        ema_sep = 0.0
        if ema8 and ema21 and ema50:
            ema_sep = abs(ema8 - ema50) / ema50
        ema_sep_norm = min(ema_sep / 0.005, 1.0)  # 0.5% separation = max (was 1%)

        # ADX = ATR * EMA_separation (both needed for trend)
        # If EMA separation is low, ADX is low regardless of ATR
        return atr_norm * ema_sep_norm

    def _compute_ema_slope_score(self, ema_slope: Dict[str, float], ema: Dict[str, float]) -> float:
        """EMA alignment and slope consistency."""
        s21 = ema_slope.get("ema21_slope", 0.0)
        s50 = ema_slope.get("ema50_slope", 0.0)

        if s21 == 0.0 and s50 == 0.0:
            # Fallback: compute from EMA values
            ema8 = ema.get("ema8", 0)
            ema21 = ema.get("ema21", 0)
            ema50 = ema.get("ema50", 0)
            if ema8 and ema21 and ema50:
                bull_align = ema8 > ema21 > ema50
                bear_align = ema8 < ema21 < ema50
                if bull_align or bear_align:
                    return 0.7
            return 0.0  # Flat = 0 score

        avg_slope = abs((s21 + s50) / 2) if s50 else abs(s21)
        return min(avg_slope / self.EMA_SLOPE_STRONG, 1.0)

    def _compute_atr_expansion_score(self, atr_pct: float, vol_spike: float) -> float:
        """Volatility regime: low ATR = range, high ATR = trending/choppy."""
        if atr_pct < self.ATR_PCT_LOW:
            return 0.1  # very low vol = range
        elif atr_pct < self.ATR_PCT_NORMAL:
            return 0.3
        elif atr_pct < self.ATR_PCT_HIGH:
            return 0.6
        else:
            # Very high ATR — could be trending or news
            return min(0.8 + vol_spike * 0.2, 1.0)

    def _compute_vwap_distance_score(self, vwap_dist: float, price: float = 0.0) -> float:
        """Distance from VWAP: far = mean reversion pressure (range/exhaustion).
        vwap_dist is absolute points, thresholds are percentages. Normalize by price.
        """
        if price <= 0:
            return 0.5  # Unknown
        dist_pct = abs(vwap_dist) / price
        if dist_pct < self.VWAP_DIST_CLOSE:
            return 0.2  # at VWAP = trend continuation likely
        elif dist_pct < self.VWAP_DIST_NORMAL:
            return 0.5
        elif dist_pct < self.VWAP_DIST_FAR:
            return 0.7
        else:
            return 0.9  # very far = exhaustion/reversion likely

    def _compute_volume_score(self, vol_ratio: float, vol_spike: float) -> float:
        """Volume participation: high = trend confirmation, low = range/weak."""
        if vol_ratio < self.VOLUME_LOW:
            return 0.2
        elif vol_ratio < self.VOLUME_NORMAL:
            return 0.4
        elif vol_ratio < self.VOLUME_HIGH:
            return 0.7
        else:
            return min(0.9 + vol_spike * 0.1, 1.0)


# Global engine instance
_global_engine = None


def get_regime_engine() -> RegimeEngine:
    """Get or create global regime engine."""
    global _global_engine
    if _global_engine is None:
        _global_engine = RegimeEngine()
    return _global_engine


def classify_regime(inputs: RegimeInputs) -> RegimeSnapshot:
    """Convenience function: classify regime using global engine."""
    engine = get_regime_engine()
    return engine.classify(inputs)