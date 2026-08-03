"""Trading Intelligence Engines — DailyGovernor v2, TradeBudget, Opportunity Lifecycle.

Production-aware execution guards. No detector logic here.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Daily Profit Governor v2
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GovernorState:
    trading_day: str = ""          # YYYY-MM-DD UTC
    day_start_equity: float = 0.0
    realized_pnl: float = 0.0      # today's realized (closed positions only)
    daily_target: float = 30.0
    daily_loss_limit: float = 50.0
    max_daily_trades: int = 100    # max closed trades per day
    trades_today: int = 0
    halted: bool = False
    halt_reason: str = ""


class DailyProfitGovernorV2:
    """Track today's PnL vs target. STOP_TRADING when target reached or loss limit hit.

    Day boundary = 00:00 UTC. Auto-resets next day. No restart needed.
    """

    def __init__(self, daily_target: float = 30.0, daily_loss_limit: float = 50.0):
        self.state = GovernorState(daily_target=daily_target, daily_loss_limit=daily_loss_limit)

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _maybe_roll_day(self):
        today = self._today()
        if self.state.trading_day != today:
            self.state.trading_day = today
            self.state.realized_pnl = 0.0
            self.state.halted = False
            self.state.halt_reason = ""

    def record_realized(self, pnl: float) -> None:
        self._maybe_roll_day()
        self.state.realized_pnl += pnl
        self.state.trades_today += 1
        if self.state.realized_pnl >= self.state.daily_target:
            self.state.halted = True
            self.state.halt_reason = f"target reached ({self.state.realized_pnl:.2f} >= {self.state.daily_target:.2f})"
        elif self.state.realized_pnl <= -self.state.daily_loss_limit:
            self.state.halted = True
            self.state.halt_reason = f"loss limit hit ({self.state.realized_pnl:.2f} <= -{self.state.daily_loss_limit:.2f})"
        elif self.state.trades_today >= self.state.max_daily_trades:
            self.state.halted = True
            self.state.halt_reason = f"max daily trades reached ({self.state.trades_today} >= {self.state.max_daily_trades})"

    def can_trade(self) -> tuple[bool, str]:
        self._maybe_roll_day()
        if self.state.halted:
            return False, self.state.halt_reason
        return True, ""


# ─────────────────────────────────────────────────────────────────────────────
# Strategy Trade Budget
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StrategyBudget:
    daily_quota: int = 5
    used: int = 0
    day: str = ""


class TradeBudgetManager:
    """Per-strategy daily trade budget. Reset at day rollover."""

    DEFAULTS = {"bystra": 100, "aggressive": 100, "semi_hft": 100}

    def __init__(self):
        self._budgets: Dict[str, StrategyBudget] = {}
        self._today = ""

    def _roll(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._today:
            self._today = today
            self._budgets = {}

    def can_consume(self, strategy: str) -> bool:
        self._roll()
        spec = self._budgets.setdefault(strategy, StrategyBudget(daily_quota=self.DEFAULTS.get(strategy, 5), day=self._today))
        return spec.used < spec.daily_quota

    def consume(self, strategy: str) -> bool:
        self._roll()
        if not self.can_consume(strategy):
            return False
        self._budgets[strategy.lower()].used += 1
        return True

    def remaining(self, strategy: str) -> int:
        self._roll()
        spec = self._budgets.get(strategy.lower())
        if not spec:
            return self.DEFAULTS.get(strategy.lower(), 5)
        return spec.daily_quota - spec.used


# ─────────────────────────────────────────────────────────────────────────────
# Opportunity Lifecycle
# ─────────────────────────────────────────────────────────────────────────────

from enum import Enum

class OppState(Enum):
    OPEN = "OPEN"
    HOT = "HOT"
    DECAYING = "DECAYING"
    EXPIRED = "EXPIRED"


@dataclass
class Opportunity:
    sig_key: str
    symbol: str
    direction: str
    confidence: float
    spread: float
    created_ts: float
    ttl: float
    state: OppState = OppState.OPEN


class OpportunityLifecycle:
    """Track signal freshness. State machine OPEN→HOT→DECAYING→EXPIRED. Signal TTL."""

    TTL_DEFAULTS = {"bystra": 120, "aggressive": 60, "semi_hft": 20}  # seconds

    def __init__(self):
        self._active: Dict[str, Opportunity] = {}
        import time; self._now = time.time

    def add(self, strategy: str, symbol: str, direction: str, confidence: float, spread: float) -> str:
        import time
        key = f"{strategy}|{symbol}|{direction}"
        ttl = self.TTL_DEFAULTS.get(strategy, 60)
        self._active[key] = Opportunity(
            sig_key=key, symbol=symbol, direction=direction,
            confidence=confidence, spread=spread,
            created_ts=time.time(), ttl=ttl,
        )
        return key

    def snapshot(self) -> Dict[str, dict]:
        import time
        now = time.time()
        out = {}
        for k, opp in list(self._active.items()):
            age = now - opp.created_ts
            ratio = age / opp.ttl
            if ratio >= 1.0:
                opp.state = OppState.EXPIRED
                del self._active[k]
                continue
            elif ratio >= 0.75:
                opp.state = OppState.DECAYING
            elif ratio >= 0.3:
                opp.state = OppState.HOT
            else:
                opp.state = OppState.OPEN
            out[k] = {"state": opp.state.value, "ttl_remaining": round(max(0, opp.ttl - age), 1)}
        return out


class DailyState(GovernorState):
    pass