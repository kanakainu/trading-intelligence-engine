import time

class AdaptiveCooldown:
    def __init__(self, base_cd=30, loss1_cd=120, loss2_cd=300):
        self.base_cd = base_cd
        self.loss1_cd = loss1_cd
        self.loss2_cd = loss2_cd
        self.consecutive_losses = 0
        self.last_trade_time = 0

    def record_trade(self, won: bool):
        self.last_trade_time = time.time()
        if won:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1

    def can_trade(self) -> bool:
        return self.remaining() <= 0

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
