"""Signal Contract — Standardized detector output.

Every detector returns Signal.
NO SL, NO TP, NO Execution.
Pure signal only.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime


class Direction(Enum):
    """Trade direction."""
    BUY = "buy"
    SELL = "sell"


class SignalStatus(Enum):
    """Signal lifecycle status."""
    RAW = "raw"           # Fresh from detector
    VALIDATED = "validated"  # Passed opportunity filter
    EXECUTED = "executed"    # Converted to ExecutionContract
    EXPIRED = "expired"      # Time passed, no entry
    CANCELLED = "cancelled"  # Invalidated before entry


@dataclass(frozen=True, slots=True)
class Signal:
    """
    Immutable signal — pure trading intent.
    
    NO stop loss, NO take profit, NO execution params.
    Detectors output this. Orchestrator enriches with SL/TP later.
    """
    # Identity (required)
    signal_id: str
    strategy: str
    symbol: str
    direction: Direction
    
    # Entry (required)
    entry_zone: Dict[str, float]
    
    # Confidence & Quality (required)
    confidence: float
    timeframe: str
    
    # Optional with defaults
    entry_price_hint: Optional[float] = None
    quality_score: float = 0.0
    regime: str = "UNKNOWN"
    opportunity_priority: int = 0
    
    # Metadata (detector-specific, free-form)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Status
    status: SignalStatus = SignalStatus.RAW
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging/transmission."""
        return {
            "signal_id": self.signal_id,
            "strategy": self.strategy,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "entry_zone": {"low": self.entry_zone["low"], "high": self.entry_zone["high"]},
            "entry_price_hint": self.entry_price_hint,
            "confidence": round(self.confidence, 3),
            "quality_score": round(self.quality_score, 3),
            "timeframe": self.timeframe,
            "regime": self.regime,
            "opportunity_priority": self.opportunity_priority,
            "metadata": self.metadata,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
    
    @property
    def entry_mid(self) -> float:
        """Midpoint of entry zone."""
        return (self.entry_zone["low"] + self.entry_zone["high"]) / 2
    
    @property
    def zone_height(self) -> float:
        """Height of entry zone in price points."""
        return abs(self.entry_zone["high"] - self.entry_zone["low"])


@dataclass(frozen=True, slots=True)
class SignalBatch:
    """Container for multiple signals from one scan."""
    scan_id: str
    symbol: str
    timestamp: datetime
    signals: tuple[Signal, ...] = ()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "count": len(self.signals),
            "signals": [s.to_dict() for s in self.signals],
        }