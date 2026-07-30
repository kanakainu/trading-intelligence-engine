#!/usr/bin/env python3
"""TIE WebSocket Server — streams live detector data, positions, PnL to dashboard."""
import asyncio, json, logging, sys
from datetime import datetime, timezone
sys.path.insert(0, '/home/ubuntu/.hermes/trading')
sys.path.insert(0, '/home/ubuntu/trading-intelligence-engine')

from gateway_client import MT5GatewayClient
from core.context.context_model import MarketContext
from strategy.orchestrator import StrategyOrchestrator

logging.basicConfig(level=logging.INFO, format='%(asctime)s TIE_WS %(message)s')
log = logging.getLogger("TIE_WS")

URL = 'https://chips-extension-extensions-wearing.trycloudflare.com'
TOKEN = 'Jojo_56790@_000tUi_OO9'
SYM = 'XAUUSD'

client = MT5GatewayClient(URL, TOKEN)
orc = StrategyOrchestrator(min_confidence=0.50)

connected = set()

async def broadcast(data):
    if connected:
        msg = json.dumps(data)
        for ws in connected.copy():
            try:
                await ws.send_text(msg)
            except:
                connected.discard(ws)

class TIEWebSocket:
    async def __call__(self, scope, receive, send):
        if scope['type'] == 'websocket':
            await self.handle_ws(scope, receive, send)
        else:
            # HTTP health check
            if scope['type'] == 'http' and scope['method'] == 'GET':
                await self.handle_http(scope, receive, send)

    async def handle_http(self, scope, receive, send):
        await send({'type': 'http.response.start', 'status': 200, 'headers': [
            (b'content-type', b'text/plain'), (b'access-control-allow-origin', b'*')
        ]})
        await send({'type': 'http.response.body', 'body': b'TIE WS OK'})

    async def handle_ws(self, scope, receive, send):
        await send({'type': 'websocket.accept'})
        connected.add(self)
        log.info(f"Client connected. Total: {len(connected)}")
        try:
            while True:
                msg = await receive()
                if msg['type'] == 'websocket.disconnect':
                    break
        finally:
            connected.discard(self)
            log.info(f"Client disconnected. Total: {len(connected)}")

async def tie_loop():
    while True:
        try:
            m5 = client.candles(SYM, "M5", 100)
            m15 = client.candles(SYM, "M15", 50)
            h1 = client.candles(SYM, "H1", 30)
            price = client.price(SYM)['ask']

            from detectors.common import find_swing_pivots, find_nearest_support, find_nearest_resistance
            pivots = find_swing_pivots(h1)
            sup = find_nearest_support(h1, price)
            res = find_nearest_resistance(h1, price)

            ctx = MarketContext(symbol=SYM, timestamp=datetime.now(timezone.utc))
            ctx.metadata.update({
                "candles": {"M5": m5, "M15": m15, "H1": h1},
                "current_price": price,
                "h1_support": sup, "h1_resistance": res,
                "h1_trend": "bullish" if h1[-1]['close'] > h1[-5]['close'] else "bearish",
                "nearest_support": sup, "nearest_resistance": res,
                "atr": (res - sup) / 20 if res and sup else 5.0,
            })

            facts = orc.run(ctx)
            best = orc.best_decision(ctx) if facts else None

            data = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "price": round(price, 2),
                "support": round(sup, 2) if sup else 0,
                "resistance": round(res, 2) if res and res < 999999 else 0,
                "trend": ctx.metadata["h1_trend"],
                "pivots": len(pivots),
                "total_setups": len(facts),
                "setups": [{
                    "detector": f.metadata.get("detector_name", "?"),
                    "name": f.value,
                    "direction": f.metadata.get("direction", "?"),
                    "confidence": round(f.confidence, 2),
                    "entry_zone_low": round(f.metadata.get("entry_zone", {}).get("low", 0), 2),
                    "entry_zone_high": round(f.metadata.get("entry_zone", {}).get("high", 0), 2),
                    "sl": round(f.metadata.get("sl", 0), 2),
                    "tp": round(f.metadata.get("tp", 0), 2),
                } for f in sorted(facts, key=lambda x: -x.confidence)],
                "best_setup": best.setup_name if best and best.action != "WAIT" else None,
                "best_action": best.action if best else "WAIT",
                "best_confidence": round(best.confidence, 2) if best else 0,
            }
            await broadcast(data)
        except Exception as e:
            log.error(f"Loop error: {e}")
        await asyncio.sleep(5)

async def main():
    import uvicorn
    config = uvicorn.Config(TIEWebSocket(), host="0.0.0.0", port=8766, log_level="warning")
    server = uvicorn.Server(config)
    # Run both server and tie_loop concurrently
    await asyncio.gather(
        server.serve(),
        tie_loop(),
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
