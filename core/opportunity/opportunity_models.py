"""Opportunity Models — OpportunitySnapshot with market filter decision."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from datetime import datetime


class OpportunityDecision(Enum):
    """Market opportunity decision."""
    ALLOWED = "allowed"
    BLOCKED = "blocked"


class BlockReason(Enum):
    """Reasons for blocking detector execution."""
    SPREAD_HIGH = "spread_high"
    ADX_LOW = "adx_low"
    NEWS_ACTIVE = "news_active"
    LOW_LIQUIDITY = "low_liquidity"
    DEAD_SESSION = "dead_session"
    ATR_LOW = "atr_low"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class OpportunitySnapshot:
    """
    Immutable market opportunity filter result.
    Evaluated BEFORE detectors execute.
    Generic — NO strategy-specific logic.
    """
    market_allowed: bool
    reason: BlockReason
    priority: int  # 0=blocked, 1-10=allowed (higher=better conditions)
    confidence: float  # 0.0-1.0

    symbol: str
    timestamp: datetime
    scan_id: str

    # Raw metrics used
    spread: float = 0.0
    atr_pct: float = 0.0
    adx: float = 0.0
    volume_ratio: float = 0.0
    session: str = ""

    def to_dict(self) -> dict:
        return {
            "market_allowed": self.market_allowed,
            "reason": self.reason.value,
            "priority": self.priority,
            "confidence": round(self.confidence, 3),
            "spread": round(self.spread, 4),
            "atr_pct": round(self.atr_pct, 4),
            "adx": round(self.adx, 2),
            "volume_ratio": round(self.volume_ratio, 2),
            "session": self.session,
        }


@dataclass(frozen=True, slots=True)
class OpportunityInputs:
    """Inputs for opportunity filter."""
    # From FeatureSnapshot
    spread: float
    atr_percent: float  # Dict[str, float] — use H1
    volume_ratio: float  # Dict[str, float] — use H1
    
    # From RegimeSnapshot (optional)
    regime_name: Optional[str] = None
    adx: float = 0.0
    
    # From market context
    current_time: Optional[datetime] = None
    symbol: str = ""
    scan_id: str = ""