import numpy as np
import pandas as pd

class RiskXRay:
    def analyze(self, result):
        trades = result.trades
        eq = result.equity_curve
        
        total_trades = len(trades)
        wins = [t for t in trades if t['pnl'] > 0]
        win_rate = len(wins) / total_trades if total_trades > 0 else 0
        
        gross_profit = sum(t['pnl'] for t in trades if t['pnl'] > 0)
        gross_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)
        
        # Sharpe
        returns = pd.Series(eq).pct_change().dropna()
        if len(returns) > 1 and returns.std() != 0:
            sharpe = (returns.mean() / returns.std()) * np.sqrt(252 * 288) # 288 M5 bars per day
        else:
            sharpe = 0
            
        # Drawdown
        peak = pd.Series(eq).expanding().max()
        dd = (pd.Series(eq) - peak) / peak
        max_dd = abs(dd.min()) * 100
        
        net_pnl = result.final_equity - eq[0]
        
        # Avg RR
        win_avg = np.mean([t['pnl'] for t in wins]) if wins else 0
        loss_avg = np.mean([abs(t['pnl']) for t in trades if t['pnl'] < 0]) if len(trades) > len(wins) else 0
        avg_rr = win_avg / loss_avg if loss_avg > 0 else 0

        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': max_dd,
            'avg_rr': avg_rr,
            'final_equity': result.final_equity,
            'net_pnl': net_pnl
        }

    def print_report(self, result):
        metrics = self.analyze(result)
        print("-" * 30)
        print(f"Backtest Report: {result.symbol} {result.timeframe}")
        print(f"Trades: {metrics['total_trades']}")
        print(f"Win Rate: {metrics['win_rate']:.2%}")
        print(f"Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"Max DD: {metrics['max_drawdown_pct']:.2f}%")
        print(f"Sharpe: {metrics['sharpe_ratio']:.2f}")
        print(f"Net PnL: {metrics['net_pnl']:.2f}")
        print(f"Final Equity: {metrics['final_equity']:.2f}")
        print("-" * 30)
