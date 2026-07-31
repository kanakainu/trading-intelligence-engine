"""Trend Capability — Interprets trend features for strategy."""

from core.capabilities.base_capability import BaseCapability
from core.features.feature_models import FeatureSnapshot


class TrendCapability(BaseCapability):
    """Trend interpretation.
    
    Exposes:
    - adx: per timeframe
    - ema_alignment: per timeframe (bullish/bearish/mixed)
    - trend_strength: per timeframe (composite 0-1)
    """
    
    def __init__(self, feature_snapshot: FeatureSnapshot):
        super().__init__(feature_snapshot)
        self._trend = feature_snapshot.trend
    
    @property
    def adx(self) -> dict[str, float]:
        """ADX per timeframe."""
        return dict(self._trend.adx)
    
    @property
    def ema_alignment(self) -> dict[str, str]:
        """EMA alignment per timeframe: 'bullish', 'bearish', 'mixed'."""
        result = {}
        for tf, ema_dict in self._trend.ema.items():
            ema8 = ema_dict.get("ema8")
            ema21 = ema_dict.get("ema21")
            ema50 = ema_dict.get("ema50")
            if ema8 is not None and ema21 is not None and ema50 is not None:
                if ema8 > ema21 > ema50:
                    result[tf] = "bullish"
                elif ema8 < ema21 < ema50:
                    result[tf] = "bearish"
                else:
                    result[tf] = "mixed"
            else:
                result[tf] = "mixed"
        return result
    
    @property
    def trend_strength(self) -> dict[str, float]:
        """Composite trend strength per timeframe (0-1).
        
        Combines ADX, EMA alignment, and trend direction.
        """
        result = {}
        for tf in self._trend.adx:
            adx = self._trend.adx.get(tf, 0)
            direction = abs(self._trend.trend_direction.get(tf, 0))
            alignment = self.ema_alignment.get(tf, "mixed")
            
            # ADX component (0-1, 25+ is trending)
            adx_component = min(1.0, adx / 50)
            
            # Direction component (0 or 1)
            dir_component = float(direction)
            
            # Alignment component
            align_map = {"bullish": 1.0, "bearish": 1.0, "mixed": 0.3}
            align_component = align_map.get(alignment, 0.3)
            
            # Weighted composite
            strength = (adx_component * 0.4) + (dir_component * 0.3) + (align_component * 0.3)
            result[tf] = min(1.0, strength)
        return result
    
    def get_adx(self, timeframe: str) -> float | None:
        """Get ADX for specific timeframe."""
        return self._trend.adx.get(timeframe)
    
    def get_ema_alignment(self, timeframe: str) -> str | None:
        """Get EMA alignment for specific timeframe."""
        return self.ema_alignment.get(timeframe)
    
    def get_trend_strength(self, timeframe: str) -> float | None:
        """Get trend strength for specific timeframe."""
        return self.trend_strength.get(timeframe)
    
    def get_ema(self, timeframe: str, period: int) -> float | None:
        """Get EMA value for timeframe and period."""
        return self._trend.ema.get(timeframe, {}).get(f"ema{period}")
    
    def get_ema_slope(self, timeframe: str, period: int) -> float | None:
        """Get EMA slope for timeframe and period."""
        return self._trend.ema_slope.get(timeframe, {}).get(f"ema{period}_slope")
    
    def get_trend_direction(self, timeframe: str) -> int | None:
        """Get trend direction for timeframe: 1=up, -1=down, 0=flat."""
        return self._trend.trend_direction.get(timeframe)
    
    def is_trending(self, timeframe: str, adx_threshold: float = 25.0) -> bool:
        """Check if market is trending on timeframe."""
        adx = self._trend.adx.get(timeframe, 0)
        return adx >= adx_threshold
    
    def is_strong_trend(self, timeframe: str, threshold: float = 0.6) -> bool:
        """Check if trend is strong on timeframe."""
        return self.get_trend_strength(timeframe) or 0 >= threshold
    
    def is_bullish_aligned(self, timeframe: str) -> bool:
        """Check if EMAs are bullish-aligned on timeframe."""
        return self.get_ema_alignment(timeframe) == "bullish"
    
    def is_bearish_aligned(self, timeframe: str) -> bool:
        """Check if EMAs are bearish-aligned on timeframe."""
        return self.get_ema_alignment(timeframe) == "bearish"
    
    def get_ema_ribbon(self, timeframe: str) -> list[float] | None:
        """Get EMA ribbon values for timeframe."""
        return self._trend.ema_ribbon.get(timeframe)
