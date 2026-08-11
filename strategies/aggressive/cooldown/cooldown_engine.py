import time

class AdaptiveCooldown:
    """Quality-based cooldown: after loss, wait for M5 recovery candle instead of fixed timer.
    Falls back to short time-gate (30s) when no M5 data available.
    """
    def __init__(self, base_cd=30, loss1_cd=120, loss2_cd=300):
        self.base_cd = base_cd
        self.loss1_cd = loss1_cd
        self.loss2_cd = loss2_cd
        self.consecutive_losses = 0
        self.last_trade_time = 0
        self.last_loss_direction = None  # "BUY" | "SELL" | None

    def record_trade(self, won: bool, direction: str | None = None):
        self.last_trade_time = time.time()
        if won:
            self.consecutive_losses = 0
            self.last_loss_direction = None
        else:
            self.consecutive_losses += 1
            self.last_loss_direction = direction

    def can_trade(self, m5_candles=None) -> bool:
        """Quality-based: after loss, require M5 recovery candle.
        Falls back to timer when no M5 data.
        """
        if self.last_trade_time == 0:
            return True
        # Minimum 30s always (avoid same-tick re-entry)
        if time.time() - self.last_trade_time < 30:
            return False
        # No recent loss → base cooldown
        if self.consecutive_losses == 0:
            return (time.time() - self.last_trade_time) >= self.base_cd
        # Loss: check M5 recovery candle
        if m5_candles and len(m5_candles) >= 2:
            c = m5_candles[-1]
            green = float(c.get("close", 0) or c.get("Close", 0)) > float(c.get("open", 0) or c.get("Open", 0))
            red   = not green
            if self.last_loss_direction == "BUY"  and green: return True
            if self.last_loss_direction == "SELL" and red:   return True
            return False  # wait for recovery candle
        # No M5 data fallback → time-based
        cd = self.loss1_cd if self.consecutive_losses == 1 else self.loss2_cd
        return (time.time() - self.last_trade_time) >= cd

    def remaining(self) -> float:
        if self.last_trade_time == 0: return 0
        if self.consecutive_losses == 0:
            cd = self.base_cd
        elif self.consecutive_losses == 1:
            cd = self.loss1_cd
        else:
            cd = self.loss2_cd
        elapsed = time.time() - self.last_trade_time
        return max(0, cd - elapsed)

if __name__ == '__main__':
    cd = AdaptiveCooldown(30, 120, 300)
    cd.record_trade(False)
    assert 110 < cd.remaining() <= 120
    cd.record_trade(False)
    assert 290 < cd.remaining() <= 300
    cd.record_trade(True)
    assert 20 < cd.remaining() <= 30
    print("AdaptiveCooldown OK")
