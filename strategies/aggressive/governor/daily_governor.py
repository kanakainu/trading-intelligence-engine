from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass
class GovernorStatus:
    halted: bool
    reason: str
    daily_pnl: float
    trades_today: int

class DailyProfitGovernor:
    def __init__(self, profit_target=30.0, max_loss=20.0):
        self.target = profit_target
        self.max_loss = max_loss
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.last_reset = datetime.now(timezone.utc).date()

    def _check_reset(self):
        now = datetime.now(timezone.utc).date()
        if now > self.last_reset:
            self.daily_pnl = 0.0
            self.trades_today = 0
            self.last_reset = now

    def record_trade(self, pnl: float):
        self._check_reset()
        self.daily_pnl += pnl
        self.trades_today += 1

    def is_halted(self) -> bool:
        self._check_reset()
        if self.daily_pnl >= self.target: return True
        if self.daily_pnl <= -self.max_loss: return True
        return False

    def get_status(self) -> dict:
        halted = self.is_halted()
        reason = "OK"
        if self.daily_pnl >= self.target: reason = "PROFIT_TARGET_REACHED"
        elif self.daily_pnl <= -self.max_loss: reason = "MAX_LOSS_REACHED"
        
        return {
            "halted": halted,
            "reason": reason,
            "daily_pnl": round(self.daily_pnl, 2),
            "trades_today": self.trades_today
        }

if __name__ == '__main__':
    gov = DailyProfitGovernor(30, 20)
    gov.record_trade(10)
    assert not gov.is_halted()
    gov.record_trade(25)
    assert gov.is_halted()
    assert gov.get_status()['reason'] == "PROFIT_TARGET_REACHED"
    print("DailyProfitGovernor OK")
