from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import List, Optional
from .market_context import Regime
from .setup_detector import SetupType

class ExecutionMode(Enum):
    RME = "RME"
    SEMIHFT = "SEMIHFT"
    NONE = "NONE"

@dataclass
class EntryDecision:
    action: str
    setup_type: SetupType
    regime: Regime
    quality_score: float
    setup_score: float
    location_score: float
    trigger_score: float
    room_score: float
    market_score: float
    execution_mode: ExecutionMode
    entry_price: float
    stop_loss: float
    take_profit: float
    initial_lot: float
    add_allowed: bool
    rejection_reason: str
    filter_trace: List[str]
    timestamp: datetime = field(default_factory=datetime.now)

    @classmethod
    def no_trade(cls, reason: str) -> 'EntryDecision':
        return cls(
            action="NONE",
            setup_type=SetupType.NONE,
            regime=Regime.UNKNOWN,
            quality_score=0.0,
            setup_score=0.0,
            location_score=0.0,
            trigger_score=0.0,
            room_score=0.0,
            market_score=0.0,
            execution_mode=ExecutionMode.NONE,
            entry_price=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            initial_lot=0.0,
            add_allowed=False,
            rejection_reason=reason,
            filter_trace=[]
        )

    @property
    def is_valid(self) -> bool:
        return self.action != "NONE" and self.quality_score >= 60.0
