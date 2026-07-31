import time
from collections import Counter

class MetricsLogger:
    def __init__(self):
        self.trades = []

    def record(self, entry_time, exit_time, pnl, exit_reason, symbol):
        self.trades.append({
            'entry_time': entry_time,
            'exit_time': exit_time,
            'pnl': pnl,
            'exit_reason': exit_reason,
            'symbol': symbol,
            'hold_seconds': exit_time - entry_time
        })

    def summary(self) -> dict:
        if not self.trades: return {}
        
        wins = [t['pnl'] for t in self.trades if t['pnl'] > 0]
        losses = [t['pnl'] for t in self.trades if t['pnl'] <= 0]
        
        total_pnl = sum(t['pnl'] for t in self.trades)
        total_hours = (time.time() - self.trades[0]['entry_time']) / 3600 if len(self.trades) > 1 else 1
        
        reasons = [t['exit_reason'] for t in self.trades]
        counts = Counter(reasons)
        total = len(self.trades)
        
        return {
            "avg_hold_seconds": round(sum(t['hold_seconds'] for t in self.trades) / total, 1),
            "avg_profit": round(sum(wins)/len(wins), 2) if wins else 0,
            "avg_loss": round(sum(losses)/len(losses), 2) if losses else 0,
            "trades_per_hour": round(total / total_hours, 2),
            "profit_per_hour": round(total_pnl / total_hours, 2),
            "exit_reasons": dict(counts),
            "timestop_pct": round(counts.get('timestop', 0) / total * 100, 1),
            "momentum_fail_pct": round(counts.get('momentum_fail', 0) / total * 100, 1)
        }

if __name__ == '__main__':
    logger = MetricsLogger()
    now = time.time()
    logger.record(now-60, now, 5.0, 'target', 'BTC')
    logger.record(now-120, now, -2.0, 'timestop', 'BTC')
    s = logger.summary()
    assert s['avg_hold_seconds'] == 90.0
    assert s['exit_reasons']['target'] == 1
    print("MetricsLogger OK")
