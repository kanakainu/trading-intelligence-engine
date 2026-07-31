"""Liquidity Capability — Interprets liquidity features for strategy."""

from core.capabilities.base_capability import BaseCapability
from core.features.feature_models import FeatureSnapshot


class LiquidityCapability(BaseCapability):
    """Liquidity interpretation.
    
    Exposes:
    - liquidity_score: 0-1 composite
    - spread_quality: "tight", "normal", "wide", "extreme"
    - session_quality: "optimal", "good", "poor", "dead"
    """
    
    def __init__(self, feature_snapshot: FeatureSnapshot):
        super().__init__(feature_snapshot)
        self._liq = feature_snapshot.liquidity
    
    @property
    def liquidity_score(self) -> float:
        """Composite liquidity score (0-1)."""
        return self._liq.liquidity_score
    
    @property
    def spread_quality(self) -> str:
        """Spread quality classification."""
        return self._liq.spread_quality
    
    @property
    def session_quality(self) -> str:
        """Session quality classification."""
        return self._liq.session_quality
    
    @property
    def spread(self) -> float:
        """Current spread."""
        return self._liq.spread
    
    @property
    def tick_speed(self) -> float:
        """Ticks per second."""
        return self._liq.tick_speed
    
    def is_liquid(self, threshold: float = 0.5) -> bool:
        """Check if market is sufficiently liquid."""
        return self._liq.liquidity_score >= threshold
    
    def is_spread_tight(self) -> bool:
        """Check if spread is tight."""
        return self._liq.spread_quality == "tight"
    
    def is_spread_wide(self) -> bool:
        """Check if spread is wide or extreme."""
        return self._liq.spread_quality in ("wide", "extreme")
    
    def is_session_optimal(self) -> bool:
        """Check if session quality is optimal."""
        return self._liq.session_quality == "optimal"
    
    def is_session_poor(self) -> bool:
        """Check if session quality is poor or dead."""
        return self._liq.session_quality in ("poor", "dead")
    
    def get_liquidity_grade(self) -> str:
        """Get letter grade for liquidity."""
        score = self._liq.liquidity_score
        if score >= 0.8:
            return "A"
        elif score >= 0.6:
            return "B"
        elif score >= 0.4:
            return "C"
        elif score >= 0.2:
            return "D"
        return "F"
    
    def get_spread_grade(self) -> str:
        """Get letter grade for spread quality."""
        mapping = {
            "tight": "A",
            "normal": "B",
            "wide": "C",
            "extreme": "F",
        }
        return mapping.get(self._liq.spread_quality, "F")
    
    def get_session_grade(self) -> str:
        """Get letter grade for session quality."""
        mapping = {
            "optimal": "A",
            "good": "B",
            "poor": "C",
            "dead": "F",
        }
        return mapping.get(self._liq.session_quality, "F")
