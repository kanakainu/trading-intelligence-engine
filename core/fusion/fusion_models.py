"""Fusion Models — ConsensusSignal and fusion metadata."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional
from datetime import datetime


class FusionDecision(Enum):
    """Result of signal fusion."""
    CONSENSUS = "consensus"      # Multiple detectors agree
    SINGLE = "single"            # Only one detector fired
    CONFLICT = "conflict"        # Opposing directions — REJECT
    DUPLICATE = "duplicate"      # Same strategy fired multiple
    NO_SIGNALS = "no_signals"    # No signals to fuse


@dataclass(frozen=True, slots=True)
class FusedSignal:
    """
    Result of fusing multiple signals.
    
    NO execution, NO risk.
    Pure fusion logic.
    """
    # Identity
    fusion_id: str
    symbol: str
    direction: str  # "buy", "sell", "conflict"
    
    # Decision
    decision: FusionDecision
    
    # Scoring
    confidence: float       # 0.0 - 1.0 (weighted average)
    agreement: float        # 0.0 - 1.0 (how aligned are signals)
    conflict_score: float   # 0.0 - 1.0 (opposing signals)
    duplicate_score: float  # 0.0 - 1.0 (same strategy overlap)
    
    # Entry zone (merged)
    entry_zone: Dict[str, float]  # {"low": ..., "high": ...}
    
    # Source signals
    source_signals: List[str] = field(default_factory=list)  # signal_ids
    strategies: List[str] = field(default_factory=list)      # unique strategies
    count: int = 0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "fusion_id": self.fusion_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "decision": self.decision.value,
            "confidence": round(self.confidence, 3),
            "agreement": round(self.agreement, 3),
            "conflict_score": round(self.conflict_score, 3),
            "duplicate_score": round(self.duplicate_score, 3),
            "entry_zone": self.entry_zone,
            "source_signals": self.source_signals,
            "strategies": self.strategies,
            "count": self.count,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class FusionInputs:
    """Inputs for signal fusion."""
    signals: List[Any]  # List[Signal] - from core.signals
    symbol: str
    scan_id: str
    timestamp: datetime = field(default_factory=datetime.now)