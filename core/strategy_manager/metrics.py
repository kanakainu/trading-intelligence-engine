"""Strategy Metrics — per-strategy performance tracking."""
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from core.strategy.strategy_result import StrategyResult


@dataclass
class StrategyMetrics:
    strategy_id: str
    signals_generated: int = 0
    signals_accepted: int = 0
    signals_rejected: int = 0
    total_confidence: float = 0.0
    wins: int = 0
    losses: int = 0
    total_hold_seconds: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    first_signal_at: Optional[datetime] = None
    last_signal_at: Optional[datetime] = None

    def record(self, result: StrategyResult) -> None:
        self.signals_generated += 1
        now = datetime.now()
        if self.first_signal_at is None:
            self.first_signal_at = now
        self.last_signal_at = now
        if result.signal:
            self.signals_accepted += 1
            self.total_confidence += result.confidence
        else:
            self.signals_rejected += 1

    def record_trade(self, pnl: float, hold_seconds: float) -> None:
        self.total_hold_seconds += hold_seconds
        if pnl > 0:
            self.wins += 1
            self.gross_profit += pnl
        else:
            self.losses += 1
            self.gross_loss += abs(pnl)

    @property
    def winrate(self) -> float:
        total = self.wins + self.losses
        return self.wins / total if total > 0 else 0.0

    @property
    def avg_confidence(self) -> float:
        return self.total_confidence / self.signals_accepted if self.signals_accepted > 0 else 0.0

    @property
    def avg_hold_time(self) -> float:
        total = self.wins + self.losses
        return self.total_hold_seconds / total if total > 0 else 0.0

    @property
    def profit_factor(self) -> float:
        return self.gross_profit / self.gross_loss if self.gross_loss > 0 else 0.0

    def summary(self) -> dict:
        return {
            "signals_generated": self.signals_generated,
            "signals_accepted": self.signals_accepted,
            "signals_rejected": self.signals_rejected,
            "winrate": round(self.winrate, 3),
            "avg_confidence": round(self.avg_confidence, 3),
            "avg_hold_time_s": round(self.avg_hold_time, 1),
            "profit_factor": round(self.profit_factor, 3),
        }
