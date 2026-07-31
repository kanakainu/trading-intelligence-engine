"""StrategyMetrics — richer per-strategy performance tracking."""
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class StrategyMetrics:
    strategy_id: str
    signals_generated: int = 0
    signals_executed: int = 0
    signals_rejected: int = 0
    wins: int = 0
    losses: int = 0
    total_rr: float = 0.0
    total_hold_seconds: float = 0.0
    total_confidence: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    max_drawdown: float = 0.0
    first_at: Optional[datetime] = None
    last_at: Optional[datetime] = None

    def record_signal(self, confidence: float, executed: bool) -> None:
        self.signals_generated += 1
        self.total_confidence += confidence
        now = datetime.now()
        if not self.first_at: self.first_at = now
        self.last_at = now
        if executed: self.signals_executed += 1
        else: self.signals_rejected += 1

    def record_trade(self, pnl: float, rr: float, hold_seconds: float) -> None:
        self.total_hold_seconds += hold_seconds
        self.total_rr += rr
        if pnl >= 0:
            self.wins += 1; self.gross_profit += pnl
        else:
            self.losses += 1; self.gross_loss += abs(pnl)

    @property
    def winrate(self) -> float:
        t = self.wins + self.losses
        return self.wins / t if t else 0.0

    @property
    def avg_rr(self) -> float:
        t = self.wins + self.losses
        return self.total_rr / t if t else 0.0

    @property
    def avg_hold_time(self) -> float:
        t = self.wins + self.losses
        return self.total_hold_seconds / t if t else 0.0

    @property
    def avg_confidence(self) -> float:
        return self.total_confidence / self.signals_generated if self.signals_generated else 0.0

    @property
    def profit_factor(self) -> float:
        return self.gross_profit / self.gross_loss if self.gross_loss else 0.0

    def summary(self) -> dict:
        return {
            "signals_generated": self.signals_generated,
            "signals_executed": self.signals_executed,
            "signals_rejected": self.signals_rejected,
            "winrate": round(self.winrate, 3),
            "avg_rr": round(self.avg_rr, 3),
            "avg_hold_time_s": round(self.avg_hold_time, 1),
            "avg_confidence": round(self.avg_confidence, 3),
            "profit_factor": round(self.profit_factor, 3),
            "max_drawdown": round(self.max_drawdown, 3),
        }
