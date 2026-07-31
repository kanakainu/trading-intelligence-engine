"""Momentum Flow Capability — Interprets momentum features for strategy."""

from core.capabilities.base_capability import BaseCapability
from core.features.feature_models import FeatureSnapshot


class MomentumFlowCapability(BaseCapability):
    """Momentum flow interpretation.
    
    Exposes:
    - impulse_score: per timeframe
    - velocity: per timeframe
    - pullback_quality: per timeframe (0-1)
    - momentum_strength: per timeframe (composite 0-1)
    """
    
    def __init__(self, feature_snapshot: FeatureSnapshot):
        super().__init__(feature_snapshot)
        self._mom = feature_snapshot.momentum
    
    @property
    def impulse_score(self) -> dict[str, float]:
        """Impulse score per timeframe (raw impulse size)."""
        return dict(self._mom.impulse_size)
    
    @property
    def velocity(self) -> dict[str, float]:
        """Price velocity per timeframe."""
        return dict(self._mom.price_velocity)
    
    @property
    def pullback_quality(self) -> dict[str, float]:
        """Pullback quality per timeframe (0-1)."""
        return dict(self._mom.pullback_quality)
    
    @property
    def momentum_strength(self) -> dict[str, float]:
        """Composite momentum strength per timeframe (0-1).
        
        Combines impulse, velocity, and pullback quality.
        """
        result = {}
        for tf in set(self._mom.impulse_size.keys()) | set(self._mom.price_velocity.keys()):
            impulse = abs(self._mom.impulse_size.get(tf, 0))
            vel = abs(self._mom.price_velocity.get(tf, 0))
            pb = self._mom.pullback_quality.get(tf, 0)
            # Normalize and combine
            strength = min(1.0, (impulse + vel) * 0.5 * (0.5 + pb * 0.5))
            result[tf] = strength
        return result
    
    def get_impulse_score(self, timeframe: str) -> float | None:
        """Get impulse score for specific timeframe."""
        return self._mom.impulse_size.get(timeframe)
    
    def get_velocity(self, timeframe: str) -> float | None:
        """Get velocity for specific timeframe."""
        return self._mom.price_velocity.get(timeframe)
    
    def get_pullback_quality(self, timeframe: str) -> float | None:
        """Get pullback quality for specific timeframe."""
        return self._mom.pullback_quality.get(timeframe)
    
    def get_momentum_strength(self, timeframe: str) -> float | None:
        """Get momentum strength for specific timeframe."""
        return self.momentum_strength.get(timeframe)
    
    def get_body_ratio(self, timeframe: str) -> float | None:
        """Get body ratio for specific timeframe."""
        return self._mom.body_ratio.get(timeframe)
    
    def get_wick_ratio(self, timeframe: str) -> float | None:
        """Get wick ratio for specific timeframe."""
        return self._mom.wick_ratio.get(timeframe)
    
    def get_momentum_score(self, timeframe: str) -> float | None:
        """Get raw momentum score for specific timeframe."""
        return self._mom.momentum_score.get(timeframe)
    
    def is_impulsive(self, timeframe: str, threshold: float = 0.6) -> bool:
        """Check if momentum is impulsive on timeframe."""
        return self.get_momentum_strength(timeframe) or 0 > threshold
    
    def is_pullback_clean(self, timeframe: str, threshold: float = 0.5) -> bool:
        """Check if pullback is clean (high quality) on timeframe."""
        return self.get_pullback_quality(timeframe) or 0 > threshold
