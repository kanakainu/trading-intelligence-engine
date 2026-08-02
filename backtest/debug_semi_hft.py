"""Debug SemiHFT filters — why 0 trade?"""
import sys
sys.path.insert(0, '/home/ubuntu/trading-intelligence-engine')
from backtest.pipeline import load
from strategies.semi_hft.market_state import classify, MarketState
from strategies.semi_hft.opportunity import evaluate, OpportunityWindow
from strategies.semi_hft.microstructure import detect, MicroSignal

df = load('XAUUSD', 'M5', 500)
rows = df.to_dict('records')

stats = {
    'total': len(rows),
    'state_sleeping': 0,
    'state_exhausted': 0,
    'state_ok': 0,
    'opp_closed': 0,
    'opp_open': 0,
    'micro_none': 0,
    'micro_signal': 0,
}

for i in range(len(rows)):
    window = rows[max(0,i-9):i+1]
    cur = rows[i]
    
    # Market state
    state_snap = classify(window, rows[:i+1])
    if state_snap.state == MarketState.SLEEPING:
        stats['state_sleeping'] += 1
        continue
    if state_snap.state == MarketState.EXHAUSTED:
        stats['state_exhausted'] += 1
        continue
    stats['state_ok'] += 1
    
    # Opportunity
    ts = cur.get('time')
    utc_hour = ts.hour if hasattr(ts, 'hour') else 12
    opp = evaluate(spread=12.0, atr_m5=cur.get('atr',0.0) or 0.0, utc_hour=utc_hour, candles_m1=window)
    if opp.window != OpportunityWindow.OPEN:
        stats['opp_closed'] += 1
        continue
    stats['opp_open'] += 1
    
    # Microstructure
    micro = detect(window)
    if micro.signal == MicroSignal.NONE:
        stats['micro_none'] += 1
    else:
        stats['micro_signal'] += 1
        print(f"Bar {i}: {micro.signal.value} pattern={micro.pattern} q={micro.quality:.2f}")

print(f"\n{'='*50}")
print("FILTER BREAKDOWN")
print(f"{'='*50}")
print(f"Total bars       : {stats['total']}")
print(f"State SLEEPING   : {stats['state_sleeping']} ({stats['state_sleeping']/stats['total']*100:.1f}%)")
print(f"State EXHAUSTED  : {stats['state_exhausted']} ({stats['state_exhausted']/stats['total']*100:.1f}%)")
print(f"State OK         : {stats['state_ok']} ({stats['state_ok']/stats['total']*100:.1f}%)")
print(f"Opp CLOSED       : {stats['opp_closed']} (of state_ok)")
print(f"Opp OPEN         : {stats['opp_open']} (of state_ok)")
print(f"Micro NONE       : {stats['micro_none']} (of opp_open)")
print(f"Micro SIGNAL     : {stats['micro_signal']} (of opp_open)")
