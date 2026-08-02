"""Sensitivity Analysis for Risk Gate RR on SemiHFT BTCUSD."""
import sys, os
sys.path.insert(0, '/home/ubuntu/trading-intelligence-engine')
from backtest.test_semi_hft import run

def sensitivity_test(symbol='BTCUSD', count=2000):
    rr_targets = [1.0, 1.2, 1.5]
    results = []

    print(f"\n{'='*60}")
    print(f"RR SENSITIVITY TEST — {symbol} {count} bars")
    print(f"{'='*60}")

    for target in rr_targets:
        # Mocking the attack_engine behavior by filtering trades in the test script result
        # Note: In real life we change attack_engine, here we filter the result to see impact
        trades, eq = run(symbol=symbol, count=count)
        
        # Filter trades that meet the RR target
        filtered_trades = [t for t in trades if t['tp'] > 0 and (abs(t['tp'] - t['entry']) / max(abs(t['entry'] - t['sl']), 0.1)) >= target - 0.05]
        
        wins = len([t for t in filtered_trades if t['pnl'] > 0])
        total = len(filtered_trades)
        wr = (wins/total*100) if total else 0
        pnl = sum(t['pnl'] for t in filtered_trades)
        
        results.append({
            'min_rr': target,
            'trades': total,
            'wr': wr,
            'pnl': pnl
        })
        print(f"Min RR {target:.1f} : Trades={total:3d} | WR={wr:5.1f}% | Net PnL=${pnl:9.2f}")

    print(f"\n{'='*60}")
    print("REKOMENDASI RIRI:")
    best = max(results, key=lambda x: x['pnl'])
    if best['pnl'] < 0:
        print("  ⚠️ Semua setting RR di strategy ini masih RUGI di BTCUSD.")
        print("  Penyebab: Logic 'expansion' & 'breakout' memang toxic di crypto.")
    else:
        print(f"  ✅ Pakai Min RR {best['min_rr']} untuk profit max.")

if __name__ == '__main__':
    sensitivity_test('BTCUSD', 2000)
