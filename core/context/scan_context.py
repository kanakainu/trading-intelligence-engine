"""ScanContext — Unified context for new TIE v2 pipeline.

Replaces MarketContext + metadata dict.
Contains: MarketContext, FeatureSnapshot, RegimeSnapshot, OpportunitySnapshot.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime
from core.features.feature_models import FeatureSnapshot
from core.regime.regime_models import RegimeSnapshot
from core.opportunity.opportunity_models import OpportunitySnapshot
from core.context.context_model import MarketContext


@dataclass(frozen=True, slots=True)
class ScanContext:
    """
    Complete scan context passed to all detectors.
    
    Detectors receive ONLY this object.
    No direct access to raw data.
    """
    # Market data
    market: MarketContext
    
    # Computed features (once per scan)
    features: FeatureSnapshot
    
    # Market regime classification
    regime: RegimeSnapshot
    
    # Pre-detector market filter
    opportunity: OpportunitySnapshot
    
    # Scan metadata
    scan_id: str
    timestamp: datetime
    
    # Convenience accessors
    @property
    def symbol(self) -> str:
        return self.market.symbol
    
    @property
    def candles(self) -> Dict[str, list]:
        return self.features.candles
    
    @property
    def current_price(self) -> float:
        return self.market.metadata.get("current_price", 0.0)
    
    @property
    def h1_support(self) -> Optional[float]:
        val = self.features.get_swing("H1", "low")
        return val if val is not None else 0.0
    
    @property
    def h1_resistance(self) -> Optional[float]:
        val = self.features.get_swing("H1", "high")
        return val if val is not None else 999999.0
    
    @property
    def atr(self) -> float:
        return self.features.get_atr("H1")
    
    @property
    def spread(self) -> float:
        return self.features.spread
    
    def get_candles(self, tf: str) -> list:
        """Get candles for timeframe."""
        return self.features.candles.get(tf, [])
    
    def is_opportunity_allowed(self) -> bool:
        """Check if market conditions allow trading."""
        return self.opportunity.market_allowed
    
    def get_regime_name(self) -> str:
        return self.regime.regime.name
    
    def get_opportunity_priority(self) -> int:
        return self.opportunity.priority


@dataclass(frozen=True, slots=True)
class ScanInputs:
    """Inputs for building ScanContext."""
    symbol: str
    candles: Dict[str, list]  # M1, M5, M15, H1
    current_price: float
    spread: float
    balance: float
    equity: float
    open_positions: int
    raw_positions: list
    scan_id: str
    timestamp: datetime