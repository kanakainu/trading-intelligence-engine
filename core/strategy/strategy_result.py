"""Strategy Result — signal + metadata from strategy execution."""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from core.signals import Signal


@dataclass(frozen=True, slots=True)
class StrategyResult:
    """Immutable strategy execution result."""
    # Output
    signal: Optional[Signal]
    
    # Quality
    confidence: float
    
    # Reason
    reason: str
    
    # Capabilities used (for audit)
    capabilities_used: List[str] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
