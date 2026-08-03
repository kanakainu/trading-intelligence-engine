"""Daily Governor — profit/loss cap, consecutive loss cooldown."""
from dataclasses import dataclass
from datetime import datetime, timezone
import time

DAILY_PROFIT_TARGET = 30.0
DAILY_LOSS_LIMIT    = 50.0
CONSEC_LOSS_COOLDOWN = 30 * 60  # 30 min in seconds

@dataclass
class GovernorStatus:
    halted:      bool
    reason:      str
    daily_pnl:   float
    trades_today: int

class DailyGovernor:
    def __init__(self):
        self._reset()

    def _reset(self):
        self.daily_pnl     = 0.0
        self.trades_today  = 0
        self.consec_losses = 0
        self._cooldown_until: float = 0.0
        self._date = datetime.now(timezone.utc).date()

    def _check_date(self):
        today = datetime.now(timezone.utc).date()
        if today != self._date:
            self._reset()

    def record_trade(self, pnl: float):
        self._check_date()
        self.daily_pnl    += pnl
        self.trades_today += 1
        if pnl < 0:
            self.consec_losses += 1
            if self.consec_losses >= 3:
                self._cooldown_until = time.time() + CONSEC_LOSS_COOLDOWN
                self.consec_losses = 0
        else:
            self.consec_losses = 0

    def is_halted(self) -> bool:
        self._check_date()
        if self.daily_pnl >= DAILY_PROFIT_TARGET: return True
        if self.daily_pnl <= -DAILY_LOSS_LIMIT:   return True
        if time.time() < self._cooldown_until:     return True
        return False

    def get_status(self) -> dict:
        self._check_date()
        reason = "ok"
        if self.daily_pnl >= DAILY_PROFIT_TARGET: reason="profit_target"
        elif self.daily_pnl <= -DAILY_LOSS_LIMIT: reason="loss_limit"
        elif time.time() < self._cooldown_until:  reason=f"cooldown_{int(self._cooldown_until-time.time())}s"
        return {"halted": self.is_halted(), "reason": reason,
                "daily_pnl": self.daily_pnl, "trades_today": self.trades_today}
