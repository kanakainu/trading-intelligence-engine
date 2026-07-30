"""Phase 8.5 — EntryMonitor integration test with live MT5 data."""
import sys, time, logging
from datetime import datetime, timezone
sys.path.insert(0, '/home/ubuntu/.hermes/trading')
from gateway_client import MT5GatewayClient
from core.context.context_model import MarketContext
from strategy.orchestrator import StrategyOrchestrator
from runtime.entry_monitor import EntryMonitor
from adapters.broker.mt5_broker import MT5BrokerAdapter
from core.decision.trade_decision import WAIT

logging.basicConfig(level=logging.INFO, format='%(name)s %(message)s')
logging.getLogger("urllib3").setLevel(logging.ERROR)

URL   = 'https://chips-extension-extensions-wearing.trycloudflare.com'
TOKEN = 'Jojo_56790@_000tUi_OO9'
SYM   = 'XAUUSD'

client = MT5GatewayClient(URL, TOKEN)
broker = MT5BrokerAdapter(base_url=URL, token=TOKEN)
broker.initialize()

orc     = StrategyOrchestrator(min_confidence=0.50)
monitor = EntryMonitor(broker=broker, gateway=client)

# --- Detect ---
candles = {
    tf: client.candles(SYM, tf, 40 if tf == "M5" else 20)
    for tf in ["M5","M15","M30","H1"]
}
price = client.price(SYM)['ask']
ctx = MarketContext(symbol=SYM, timestamp=datetime.now(timezone.utc))
ctx.metadata.update({
    "candles": candles,
    "current_price": price,
    "atr": 5.0,
    "h1_support": price - 15.0,
    "h1_resistance": price + 15.0,
    "h1_trend": "bearish",
    "nearest_support": price - 1.0,
    "nearest_resistance": price + 1.0,
})

decision = orc.best_decision(ctx)
print(f"\n[DETECTOR] action={decision.action} setup={decision.setup_name} conf={decision.confidence:.0%}")
print(f"  {decision.explanation}")

if decision.action == WAIT:
    print("No setup → exit")
    sys.exit(0)

# --- Add to monitor ---
monitor.add_setup(decision)
print(f"\n[MONITOR] Watchlist: {len(monitor.watchlist)} setups")
for s in monitor.watchlist:
    print(f"  {s.setup_name} {s.direction} zone={s.entry_zone} dz={s.danger_zone} sl={s.sl}")

# --- Simulate 5 ticks ---
print("\n[MONITOR] Simulating 5 price ticks...")
for i in range(5):
    monitor.update()
    current = client.price(SYM)['bid']
    print(f"  tick {i+1}: price={current:.3f} watchlist={len(monitor.watchlist)}")
    time.sleep(1)

print("\nDone. EntryMonitor wired OK.")
