"""Trade Lifecycle Models — State machine for position lifecycle."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime


class LifecycleState(Enum):
    """Position lifecycle states."""
    PENDING = "pending"        # Not yet filled
    OPEN = "open"              # Filled, no modifications
    PARTIAL = "partial"        # Partial TP taken
    BREAKEVEN = "breakeven"    # SL moved to breakeven
    TRAILING = "trailing"      # Trailing stop active
    TIMEOUT = "timeout"        # Entry timeout, no fill
    CLOSED = "closed"          # Position closed
    REFLECTION = "reflection"  # Post-trade analysis


@dataclass
class PositionSnapshot:
    """Immutable snapshot of position at a moment in time."""
    position_id: str
    symbol: str
    direction: str
    
    # Current state
    state: LifecycleState
    entry_price: Optional[float]
    current_price: float
    
    # Risk
    sl: Optional[float]
    tp: Optional[float]
    danger_zone: Optional[float]
    
    # Size
    volume: float
    volume_remaining: float
    
    # P&L
    floating_pl: float
    realized_pl: float
    
    # Timing
    opened_at: Optional[datetime]
    closed_at: Optional[datetime]
    duration_seconds: float
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class LifecycleEvent:
    """Immutable event in position lifecycle."""
    event_id: str
    position_id: str
    event_type: str  # "entry", "partial", "breakeven", "trailing", "exit", "timeout"
    
    # State transition
    old_state: LifecycleState
    new_state: LifecycleState
    
    # Trigger
    trigger: str  # "price", "time", "manual", "rule"
    trigger_value: Any
    
    # Details
    price: Optional[float]
    volume: Optional[float]
    pl: Optional[float]
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)