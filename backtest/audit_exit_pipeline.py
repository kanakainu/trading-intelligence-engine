"""Exit Pipeline Audit — Map SL/TP/Trail/Entry across 3 strategies."""
import sys
sys.path.insert(0, '/home/ubuntu/trading-intelligence-engine')

print("=" * 70)
print("EXIT PIPELINE AUDIT — 3 Strategy")
print("=" * 70)

# Strategy 1: SemiHFT
print("\n1. SEMI_HFT")
print("   Metadata:", end=" ")
from strategies.semi_hft.strategy import METADATA as semi_meta
print(f"{semi_meta.id}, v{semi_meta.version}, symbols={semi_meta.supported_symbols}")
print("   Entry logic: strategies/semi_hft/microstructure.py (detect)")
print("   SL/TP calc: strategies/semi_hft/attack_engine.py (plan)")
print("     - SL: _swing_pivot(candles_m1) ± SL_BUFFER(1.5)")
print("     - TP: sl_dist * 1.5, capped MIN_TP=1.5, MAX_TP=3.0")
print("     - RR: tp_dist / sl_dist")
print("   Exit mgmt: strategies/semi_hft/exit_engine.py")
try:
    with open('/home/ubuntu/trading-intelligence-engine/strategies/semi_hft/exit_engine.py') as f:
        print("     [EXISTS]")
except:
    print("     [NOT FOUND — using default engine]")
print("   Trailing: strategies/semi_hft/position_manager.py")
try:
    with open('/home/ubuntu/trading-intelligence-engine/strategies/semi_hft/position_manager.py') as f:
        print("     [EXISTS]")
except:
    print("     [NOT FOUND]")

# Strategy 2: Aggressive
print("\n2. AGGRESSIVE")
print("   Metadata:", end=" ")
from strategies.aggressive.strategy import AggressiveStrategy
agg = AggressiveStrategy()
print(f"{agg.metadata.id}, v{agg.metadata.version}, symbols={agg.metadata.supported_symbols}")
print("   Entry logic: strategies/aggressive/detectors/ (multiple)")
print("   SL/TP calc: ???")
import os
agg_files = os.listdir('/home/ubuntu/trading-intelligence-engine/strategies/aggressive')
if 'attack_engine.py' in agg_files:
    print("     - strategies/aggressive/attack_engine.py")
else:
    print("     - [NO attack_engine.py — check strategy.py]")
print("   Exit mgmt: strategies/aggressive/exits/")
exit_files = os.listdir('/home/ubuntu/trading-intelligence-engine/strategies/aggressive/exits')
print(f"     {len(exit_files)} modules:", exit_files[:5])
print("   Trailing: strategies/aggressive/exits/ (likely)")

# Strategy 3: Bystra
print("\n3. BYSTRA")
print("   Metadata:", end=" ")
from strategies.bystra.strategy import BystraStrategy
bystra = BystraStrategy()
print(f"{bystra.metadata.id}, v{bystra.metadata.version}, symbols={bystra.metadata.supported_symbols}")
print("   Entry logic: strategies/bystra/detectors/")
bystra_det = os.listdir('/home/ubuntu/trading-intelligence-engine/strategies/bystra/detectors')
print(f"     {len(bystra_det)} detectors:", bystra_det)
print("   SL/TP calc: strategies/bystra/strategy.py (analyze method)")
print("   Exit mgmt: strategies/bystra/ (check for exit_engine)")
bystra_files = os.listdir('/home/ubuntu/trading-intelligence-engine/strategies/bystra')
if 'exit_engine.py' in bystra_files:
    print("     - strategies/bystra/exit_engine.py")
else:
    print("     - [NO exit_engine — inline in strategy.py]")
print("   Trailing: [check strategy.py]")

print("\n" + "=" * 70)
print("CORE RISK GATE")
print("=" * 70)
print("   Location: core/rules/risk/")
risk_files = os.listdir('/home/ubuntu/trading-intelligence-engine/core/rules/risk')
print(f"   {len(risk_files)} rules:", [f for f in risk_files if f.endswith('.py') and f != '__init__.py'])
print("   Registry: core/rules/risk/risk_registry.py")
print("   RR enforcement: rr_rule.py (min_rr=1.5)")
print("   Spread: spread_rule.py (max_spread=800)")

print("\n" + "=" * 70)
print("FINDING: WHO CONTROLS EXIT?")
print("=" * 70)
print("SemiHFT: attack_engine.py hardcode MAX_TP=3.0")
print("         → blocks long TP, kills RR in volatile symbol")
print("Aggressive: exits/ folder (modular exit managers)")
print("         → likely adaptive")
print("Bystra: inline in strategy.py")
print("         → check if adaptive or hardcode")
print("\nRisk Gate: universal min_rr=1.5")
print("         → kills strategy if attack_engine produce <1.5")
print("\nRECOMMEND:")
print("  1. Remove MAX_TP cap from SemiHFT attack_engine")
print("  2. Add ExitManager layer before Risk Gate")
print("     - read strategy.exit_config (per-strategy RR target)")
print("     - if RR < target: widen TP OR trail aggressive")
print("     - pass adjusted plan to Risk Gate")
print("  3. Strategy register exit_config in metadata")
