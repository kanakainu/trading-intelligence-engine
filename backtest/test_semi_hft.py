"""Backtest SemiHFT C8 on XAUUSD M5 — bridge adapter."""
import sys, json, datetime
sys.path.insert(0, '/home/ubuntu/trading-intelligence-engine')
from backtest.pipeline import load
from strategies.semi_hft import strategy as semi_hft_mod
from strategies.semi_hft.market_state import classify as classify_state, MarketState
from strategies.semi_hft.opportunity import evaluate as eval_opp, OpportunityWindow
from strategies.semi_hft.microstructure import detect as detect_micro, MicroSignal
from strategies.semi_hft.entry_validator import validate as validate_entry
from strategies.semi_hft.attack_engine import plan as attack_plan

def run(symbol='XAUUSD', timeframe='M5', count=500, initial_equity=10000.0):
    if count > 1000:
        df1 = load(symbol, timeframe, 1000)
        df2 = load(symbol, timeframe, count - 1000)
        import pandas as pd
        df = pd.concat([df1, df2], ignore_index=True).drop_duplicates(subset='time').sort_values('time').reset_index(drop=True)
    else:
        df = load(symbol, timeframe, count)
    rows = df.to_dict('records')
    
    candles_m5 = rows
    trades = []
    wins = 0
    losses = 0
    equity = initial_equity
    equity_curve = [equity]
    
    for i in range(len(rows)):
        # Build M1-ish window from last bars (M5 data, simulate)
        window = rows[max(0, i-9):i+1]
        cur = rows[i]
        spread = 12.0  # typical XAUUSD M5
        atr_m5 = cur.get('atr', 0.0) or 0.0
        
        # Market state
        state_snap = classify_state(window, candles_m5[:i+1])
        if state_snap.state in (MarketState.SLEEPING, MarketState.EXHAUSTED):
            continue
        
        # Opportunity window
        ts = cur.get('time')
        utc_hour = ts.hour if hasattr(ts, 'hour') else 12
        opp = eval_opp(spread=spread, atr_m5=atr_m5, utc_hour=utc_hour, candles_m1=window)
        if opp.window != OpportunityWindow.OPEN:
            continue
        
        # Microstructure
        micro = detect_micro(window)
        if micro.signal == MicroSignal.NONE:
            continue
        
        # Entry validate
        entry = validate_entry(state_snap, opp, micro)
        if not entry.valid:
            continue
        
        # Attack plan
        price = float(cur['close'])
        ap = attack_plan(micro.signal, price, window, equity, micro.pattern)
        
        # Simulate exit: check next bars for SL/TP hit
        direction = 1 if micro.signal == MicroSignal.BUY else -1
        exit_price = None
        exit_reason = None
        for j in range(i+1, min(i+30, len(rows))):
            bar = rows[j]
            if direction == 1:
                if float(bar['low']) <= ap.sl:
                    exit_price, exit_reason = ap.sl, 'SL'
                    break
                if float(bar['high']) >= ap.tp:
                    exit_price, exit_reason = ap.tp, 'TP'
                    break
            else:
                if float(bar['high']) >= ap.sl:
                    exit_price, exit_reason = ap.sl, 'SL'
                    break
                if float(bar['low']) <= ap.tp:
                    exit_price, exit_reason = ap.tp, 'TP'
                    break
        
        if exit_price is None:
            exit_price = float(rows[min(i+29, len(rows)-1)]['close'])
            exit_reason = 'TIMEOUT'
        
        pnl = (exit_price - price) * direction * ap.lot * 100  # XAUUSD $/pt
        equity += pnl
        equity_curve.append(equity)
        
        if pnl > 0:
            wins += 1
        else:
            losses += 1
        
        trades.append({
            'i': i, 'time': str(ts), 'signal': micro.signal.value,
            'pattern': micro.pattern, 'quality': round(micro.quality, 2),
            'entry': round(price, 2), 'sl': ap.sl, 'tp': ap.tp,
            'lot': ap.lot, 'exit': round(exit_price, 2), 'reason': exit_reason,
            'pnl': round(pnl, 2)
        })
    
    total = wins + losses
    win_rate = (wins/total*100) if total else 0
    max_dd = 0
    peak = initial_equity
    for e in equity_curve:
        if e > peak: peak = e
        dd = (peak - e)/peak*100
        if dd > max_dd: max_dd = dd
    
    print(f"\n{'='*60}")
    print(f"SEMI-HFT C8 BACKTEST — {symbol} {timeframe}")
    print(f"{'='*60}")
    print(f"Bars scanned : {count}")
    print(f"Trades       : {total}")
    print(f"Win Rate     : {win_rate:.1f}%  ({wins}W/{losses}L)")
    print(f"Final Equity : ${equity:,.2f}  (init ${initial_equity:,.0f})")
    print(f"Net P&L      : ${equity - initial_equity:,.2f}")
    print(f"Max DD       : {max_dd:.2f}%")
    print(f"\nPattern breakdown:")
    patterns = {}
    for t in trades:
        p = t['pattern']
        patterns.setdefault(p, {'n':0,'w':0,'pnl':0.0})
        patterns[p]['n'] += 1
        patterns[p]['w'] += 1 if t['pnl']>0 else 0
        patterns[p]['pnl'] += t['pnl']
    for p, v in sorted(patterns.items(), key=lambda x: -x[1]['pnl']):
        wr = v['w']/v['n']*100
        print(f"  {p:14s} n={v['n']:3d}  WR={wr:5.1f}%  PnL=${v['pnl']:9.2f}")
    
    print(f"\nExit reasons:")
    reasons = {}
    for t in trades:
        reasons.setdefault(t['reason'], 0)
        reasons[t['reason']] += 1
    for r, n in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"  {r:8s} : {n}")
    
    return trades, equity_curve

if __name__ == '__main__':
    import sys
    symbol = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    trades, eq = run(symbol=symbol, count=2000)
    # Save JSON report
    out = '/home/ubuntu/trading-intelligence-engine/backtest/reports/semi_hft_c8_xauusd_m5.json'
    import os
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w') as f:
        json.dump({'trades': trades, 'final_equity': eq[-1]}, f, indent=2)
    print(f"\nReport: {out}")
