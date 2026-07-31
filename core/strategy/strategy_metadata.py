"""Strategy Metadata — identity & capability declarations."""
from dataclasses import dataclass, field
from typing import List
from datetime import datetime


@dataclass(frozen=True, slots=True)
class StrategyMetadata:
    """Immutable strategy identity."""
    id: str
    name: str
    version: str
    author: str
    description: str
    
    # Capability
    supported_symbols: List[str] = field(default_factory=list)
    supported_timeframes: List[str] = field(default_factory=list)
    supported_regimes: List[str] = field(default_factory=list)
    
    # Runtime
    priority: int = 50
    enabled: bool = True
    
    # Risk
    default_risk_pct: float = 1.0
    max_positions: int = 3
    min_balance: float = 100.0
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
