#!/usr/bin/env python3
"""TIE Production Runtime — EntryMonitor + StrategyOrchestrator live."""
import sys, time, logging
from datetime import datetime, timezone
sys.path.insert(0, '/home/ubuntu/.hermes/trading')
sys.path.insert(0, '/home/ubuntu/trading-intelligence-engine')

from gateway_client import MT5GatewayClient
from core.context.context_model import MarketContext
from strategy.orchestrator import StrategyOrchestrator
from runtime.entry_monitor import EntryMonitor
from adapters.broker.mt5_broker import MT5BrokerAdapter
from runtime.hck_wire import push_decision, push_trade

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(message)s')
log = logging.getLogger("TIE_Production")

URL = 'https://chips-extension-extensions-wearing.trycloudflare.com'
TOKEN = 'Jojo_56790@_000tUi_OO9'
SYM = 'XAUUSD'

client = MT5GatewayClient(URL, TOKEN)
broker = MT5BrokerAdapter(base_url=URL, token=TOKEN)
broker.initialize()

orc = StrategyOrchestrator(min_confidence=0.55)
monitor = EntryMonitor(broker=broker, gateway=client)

log.info("TIE Production started.")

while True:
    try:
        log.info("Fetching live candles...")
        candles = {}
        for tf in ["M5", "M15", "M30", "H1"]:
            count = 40 if tf == "M5" else 20
            candles[tf] = client.candles(SYM, tf, count)
            log.info(f"  {tf}: {len(candles[tf])} candles")
        
        price = client.price(SYM)['ask']
        log.info(f"Price: {price:.2f}")
        
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

        # Detect
        decision = orc.best_decision(ctx)
        if decision.action != "WAIT":
            log.info(f"Setup detected: {decision.setup_name} {decision.action} conf={decision.confidence:.0%}")
            push_decision(decision)
            monitor.add_setup(decision)
        else:
            log.info("No setup detected (WAIT)")

        # Monitor entries
        monitor.update()

        time.sleep(10) # Poll every 10s
    except KeyboardInterrupt:
        log.info("Stopping TIE Production.")
        break
    except Exception as e:
        log.error(f"Runtime error: {e}")
        time.sleep(30)
