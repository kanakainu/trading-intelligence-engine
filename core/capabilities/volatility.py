"""Volatility Capability — Interprets volatility features for strategy."""

from core.capabilities.base_capability import BaseCapability
from core.features.feature_models import FeatureSnapshot


class VolatilityCapability(BaseCapability):
    """Volatility interpretation.
    
    Exposes:
    - atr_expansion: per timeframe (ATR / ATR_MA)
    - volatility_regime: per timeframe ("low", "normal", "high", "extreme")
    - atr_percentile: per timeframe (0-1, where is current ATR in historical distribution)
    """
    
    def __init__(self, feature_snapshot: FeatureSnapshot):
        super().__init__(feature_snapshot)
        self._vol = feature_snapshot.volatility
        self._stats = feature_snapshot.statistics
    
    @property
    def atr_expansion(self) -> dict[str, float]:
        """ATR expansion per timeframe: current ATR / ATR moving average."""
        return dict(self._vol.atr_expansion)
    
    @property
    def volatility_regime(self) -> dict[str, str]:
        """Volatility regime per timeframe: 'low', 'normal', 'high', 'extreme'."""
        return dict(self._vol.volatility_regime)
    
    @property
    def atr_percentile(self) -> dict[str, float]:
        """ATR percentile per timeframe (0-1).
        
        Computed from raw ATR history if available, else estimated from regime.
        """
        result = {}
        for tf in self._vol.atr:
            regime = self._vol.volatility_regime.get(tf, "normal")
            # Map regime to approximate percentile
            regime_map = {
                "low": 0.15,
                "normal": 0.5,
                "high": 0.8,
                "extreme": 0.95,
            }
            result[tf] = regime_map.get(regime, 0.5)
        return result
    
    def get_atr_expansion(self, timeframe: str) -> float | None:
        """Get ATR expansion for specific timeframe."""
        return self._vol.atr_expansion.get(timeframe)
    
    def get_volatility_regime(self, timeframe: str) -> str | None:
        """Get volatility regime for specific timeframe."""
        return self._vol.volatility_regime.get(timeframe)
    
    def get_atr_percentile(self, timeframe: str) -> float | None:
        """Get ATR percentile for specific timeframe."""
        return self.atr_percentile.get(timeframe)
    
    def get_atr(self, timeframe: str) -> float | None:
        """Get ATR value for specific timeframe."""
        return self._vol.atr.get(timeframe)
    
    def get_atr_percent(self, timeframe: str) -> float | None:
        """Get ATR% (ATR/price * 100) for specific timeframe."""
        return self._vol.atr_percent.get(timeframe)
    
    def get_true_range(self, timeframe: str) -> float | None:
        """Get true range for specific timeframe."""
        return self._vol.true_range.get(timeframe)
    
    def is_expanding(self, timeframe: str, threshold: float = 1.2) -> bool:
        """Check if volatility is expanding on timeframe."""
        return self._vol.atr_expansion.get(timeframe, 1.0) >= threshold
    
    def is_contracting(self, timeframe: str, threshold: float = 0.8) -> bool:
        """Check if volatility is contracting on timeframe."""
        return self._vol.atr_expansion.get(timeframe, 1.0) <= threshold
    
    def is_low_vol(self, timeframe: str) -> bool:
        """Check if volatility regime is low."""
        return self._vol.volatility_regime.get(timeframe) == "low"
    
    def is_high_vol(self, timeframe: str) -> bool:
        """Check if volatility regime is high or extreme."""
        return self._vol.volatility_regime.get(timeframe) in ("high", "extreme")
    
    def is_extreme_vol(self, timeframe: str) -> bool:
        """Check if volatility regime is extreme."""
        return self._vol.volatility_regime.get(timeframe) == "extreme"
    
    def get_volatility_grade(self, timeframe: str) -> str:
        """Get letter grade for volatility favorability (low vol = A for mean reversion, high vol = A for breakout)."""
        regime = self._vol.volatility_regime.get(timeframe, "normal")
        mapping = {
            "low": "A",
            "normal": "B",
            "high": "C",
            "extreme": "D",
        }
        return mapping.get(regime, "B")
    
    def get_raw_atr_history(self, timeframe: str) -> list[float] | None:
        """Get raw ATR history for timeframe (for percentile calculation)."""
        return self._stats.raw_atr.get(timeframe)
