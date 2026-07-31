"""Market Structure Capability — Interprets structure features for strategy."""

from core.capabilities.base_capability import BaseCapability
from core.features.feature_models import FeatureSnapshot


class MarketStructureCapability(BaseCapability):
    """Market structure interpretation.
    
    Exposes:
    - trend_direction: per timeframe (1=up, -1=down, 0=flat)
    - nearest_support: per timeframe
    - nearest_resistance: per timeframe
    - market_bias: per timeframe ("bullish", "bearish", "neutral")
    - structure_strength: per timeframe (0-1)
    """
    
    def __init__(self, feature_snapshot: FeatureSnapshot):
        super().__init__(feature_snapshot)
        self._struct = feature_snapshot.structure
    
    @property
    def trend_direction(self) -> dict[str, int]:
        """Trend direction per timeframe: 1=up, -1=down, 0=flat."""
        return dict(self._struct.market_structure)  # type: ignore[return-value]
    
    @property
    def nearest_support(self) -> dict[str, float]:
        """Nearest support level per timeframe."""
        return dict(self._struct.nearest_support)
    
    @property
    def nearest_resistance(self) -> dict[str, float]:
        """Nearest resistance level per timeframe."""
        return dict(self._struct.nearest_resistance)
    
    @property
    def market_bias(self) -> dict[str, str]:
        """Market bias per timeframe: 'bullish', 'bearish', 'neutral'."""
        return dict(self._struct.market_structure)
    
    @property
    def structure_strength(self) -> dict[str, float]:
        """Structure strength per timeframe (0-1)."""
        return dict(self._struct.structure_strength)
    
    def get_trend_direction(self, timeframe: str) -> int | None:
        """Get trend direction for specific timeframe."""
        return self._struct.market_structure.get(timeframe)
    
    def get_nearest_support(self, timeframe: str) -> float | None:
        """Get nearest support for specific timeframe."""
        return self._struct.nearest_support.get(timeframe)
    
    def get_nearest_resistance(self, timeframe: str) -> float | None:
        """Get nearest resistance for specific timeframe."""
        return self._struct.nearest_resistance.get(timeframe)
    
    def get_market_bias(self, timeframe: str) -> str | None:
        """Get market bias for specific timeframe."""
        return self._struct.market_structure.get(timeframe)
    
    def get_structure_strength(self, timeframe: str) -> float | None:
        """Get structure strength for specific timeframe."""
        return self._struct.structure_strength.get(timeframe)
    
    def is_bullish(self, timeframe: str) -> bool:
        """Check if market structure is bullish on timeframe."""
        return self._struct.market_structure.get(timeframe) == "bullish"
    
    def is_bearish(self, timeframe: str) -> bool:
        """Check if market structure is bearish on timeframe."""
        return self._struct.market_structure.get(timeframe) == "bearish"
    
    def is_neutral(self, timeframe: str) -> bool:
        """Check if market structure is neutral on timeframe."""
        return self._struct.market_structure.get(timeframe) == "neutral"
    
    def get_swing_high(self, timeframe: str) -> float | None:
        """Get last swing high for timeframe."""
        return self._struct.last_swing_high.get(timeframe)
    
    def get_swing_low(self, timeframe: str) -> float | None:
        """Get last swing low for timeframe."""
        return self._struct.last_swing_low.get(timeframe)
    
    def get_all_supports(self, timeframe: str) -> list[float]:
        """Get all support levels for timeframe."""
        return list(self._struct.supports.get(timeframe, []))
    
    def get_all_resistances(self, timeframe: str) -> list[float]:
        """Get all resistance levels for timeframe."""
        return list(self._struct.resistances.get(timeframe, []))
    
    def get_pivot_levels(self, timeframe: str) -> dict[str, float] | None:
        """Get pivot levels for timeframe."""
        return self._struct.pivot_levels.get(timeframe)
