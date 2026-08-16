"""Context Model — generic market state, no trading logic."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Trend(str, Enum):
    BULLISH  = "bullish"
    BEARISH  = "bearish"
    SIDEWAYS = "sideways"
    UNKNOWN  = "unknown"


class Session(str, Enum):
    ASIA     = "asia"
    LONDON   = "london"
    NEW_YORK = "new_york"
    OVERLAP  = "overlap"
    CLOSED   = "closed"


class Volatility(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


class MarketStatus(str, Enum):
    OPEN   = "open"
    CLOSED = "closed"


@dataclass
class MarketContext:
    symbol:        str
    timestamp:     datetime
    price:         float         = 0.0
    vwap_z_score:  float         = 0.0
    trend:         Trend         = Trend.UNKNOWN
    session:       Session       = Session.CLOSED
    atr:           float         = 0.0
    spread:        float         = 0.0
    volatility:    Volatility    = Volatility.LOW
    market_status: MarketStatus  = MarketStatus.CLOSED
    metadata:      dict          = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "symbol":        self.symbol,
            "timestamp":     self.timestamp.isoformat(),
            "price":         self.price,
            "vwap_z_score":  self.vwap_z_score,
            "trend":         self.trend,
            "session":       self.session,
            "atr":           self.atr,
            "spread":        self.spread,
            "volatility":    self.volatility,
            "market_status": self.market_status,
            "metadata":      self.metadata,
        }
