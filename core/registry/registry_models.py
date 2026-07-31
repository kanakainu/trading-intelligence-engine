"""Strategy Registry Models — Strategy metadata and registration."""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable
from datetime import datetime


@dataclass(frozen=True, slots=True)
class StrategyMetadata:
    """Immutable strategy metadata for registry."""
    name: str
    version: str
    description: str
    author: str
    
    # Requirements
    min_balance: float = 100.0
    supported_symbols: list[str] = field(default_factory=lambda: ["XAUUSD"])
    supported_sessions: list[str] = field(default_factory=lambda: ["LONDON", "NY"])
    
    # Configuration
    default_risk_pct: float = 1.0
    default_max_positions: int = 3
    
    # Metadata
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "min_balance": self.min_balance,
            "supported_symbols": self.supported_symbols,
            "supported_sessions": self.supported_sessions,
            "default_risk_pct": self.default_risk_pct,
            "default_max_positions": self.default_max_positions,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class StrategyEntry:
    """Registry entry for a strategy."""
    metadata: StrategyMetadata
    factory: Callable  # Function that returns strategy instance
    enabled: bool = True