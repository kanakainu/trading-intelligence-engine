"""EntryDecision — structured output replacing raw signals."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List
from shared.setup_detector import SetupType
from shared.market_context import Regime


class ExecutionMode(str, Enum):
    RME     = "RME"      # Aggressive — faster trigger, lower confirmation
    SEMIHFT = "SEMIHFT"  # SemiHFT — M1 micro timing
    NONE    = "NONE"


@dataclass
class EntryDecision:
    action:           str            # BUY | SELL | NONE
    setup_type:       SetupType
    regime:           Regime
    quality_score:    float          # 0–100 total
    setup_score:      float          # 0–30
    location_score:   float          # 0–25
    trigger_score:    float          # 0–25
    room_score:       float          # 0–10
    market_score:     float          # 0–10
    execution_mode:   ExecutionMode
    entry_price:      float
    stop_loss:        float
    take_profit:      float
    initial_lot:      float
    add_allowed:      bool
    rejection_reason: str
    filter_trace:     List[str] = field(default_factory=list)
    timestamp:        datetime = field(default_factory=datetime.utcnow)

    @property
    def is_valid(self) -> bool:
        return self.action != "NONE" and self.quality_score >= 60.0

    @classmethod
    def no_trade(cls, reason: str) -> "EntryDecision":
        return cls(
            action="NONE", setup_type=SetupType.NONE, regime=Regime.UNKNOWN,
            quality_score=0.0, setup_score=0.0, location_score=0.0,
            trigger_score=0.0, room_score=0.0, market_score=0.0,
            execution_mode=ExecutionMode.NONE,
            entry_price=0.0, stop_loss=0.0, take_profit=0.0,
            initial_lot=0.0, add_allowed=False,
            rejection_reason=reason, filter_trace=[f"REJECTED:{reason}"],
        )
