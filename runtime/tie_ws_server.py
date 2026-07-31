#!/usr/bin/env python3
"""TIE WebSocket Server — Robust Async with Gateway Caching."""
import asyncio, json, logging, sys, time
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

sys.path.insert(0, '/home/ubuntu/.hermes/trading')
sys.path.insert(0, '/home/ubuntu/trading-intelligence-engine')

from gateway_client import MT5GatewayClient
from core.context.context_model import MarketContext
from strategy.orchestrator import StrategyOrchestrator
from detectors.common import find_nearest_support, find_nearest_resistance

logging.basicConfig(level=logging.INFO, format='%(asctime)s TIE_WS %(message)s')
log = logging.getLogger("TIE_WS")

URL = 'https://chips-extension-extensions-wearing.trycloudflare.com'
TOKEN = 'Jojo_56790@_000tUi_OO9'
SYM = 'XAUUSD'

# Global State
client = MT5GatewayClient(URL, TOKEN, timeout=5) # Tight timeout for WS responsiveness
orc = StrategyOrchestrator(min_confidence=0.50)
CACHE = {"data": {}, "last_update": None, "status": "INITIALIZING"}

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        log.info(f"Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        log.info(f"Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        if not self.active_connections: return
        data = json.dumps(message)
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(data)
            except Exception:
                self.active_connections.remove(connection)

manager = ConnectionManager()

async def fetch_gateway_data():
    """Background task to fetch data from MT5 Gateway (via threads to avoid blocking)."""
    loop = asyncio.get_event_loop()
    while True:
        try:
            # Parallel fetch via threads since gateway_client is synchronous (requests)
            tasks = [
                loop.run_in_executor(None, client.candles, SYM, "M5", 50),
                loop.run_in_executor(None, client.candles, SYM, "M15", 30),
                loop.run_in_executor(None, client.candles, SYM, "H1", 20),
                loop.run_in_executor(None, client.price, SYM),
                loop.run_in_executor(None, client.account),
                loop.run_in_executor(None, client.positions),
            ]
            m5, m15, h1, price_data, acc, positions = await asyncio.gather(*tasks)
            
            price = price_data['ask']
            sup = find_nearest_support(h1, price)
            res = find_nearest_resistance(h1, price)
            
            ctx = MarketContext(symbol=SYM, timestamp=datetime.now(timezone.utc))
            ctx.metadata.update({
                "candles": {"M5": m5, "M15": m15, "H1": h1},
                "current_price": price,
                "h1_support": sup, "h1_resistance": res,
                "h1_trend": "bullish" if h1[-1]['close'] > h1[-5]['close'] else "bearish",
                "nearest_support": sup, "nearest_resistance": res,
                "atr": 5.0, # Default for now
            })
            
            facts = orc.run(ctx)
            best = orc.best_decision(ctx)
            
            CACHE["data"] = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "price": round(price, 2),
                "support": round(sup, 2) if sup else 0,
                "resistance": round(res, 2) if res and res < 999999 else 0,
                "trend": ctx.metadata["h1_trend"],
                "balance": float(acc.get("balance", 0)),
                "equity": float(acc.get("equity", 0)),
                "floating_pnl": float(acc.get("profit", 0)),
                "margin_percent": float(acc.get("margin_level", 0)),
                "spread": round(price_data.get("spread", 0), 2),
                "positions": [{
                    "side": p.get("type", "").upper(),
                    "volume": p.get("volume", 0),
                    "entry": p.get("price_open", 0),
                    "sl": p.get("sl", 0),
                    "tp": p.get("tp", 0),
                    "pnl": p.get("profit", 0)
                } for p in positions],
                "total_setups": len(facts),
                "setups": [{
                    "name": f.value,
                    "direction": f.metadata.get("direction", "?"),
                    "confidence": round(f.confidence, 2),
                    "sl": round(f.metadata.get("sl", 0), 2),
                    "tp": round(f.metadata.get("tp", 0), 2),
                } for f in sorted(facts, key=lambda x: -x.confidence)],
                "best_setup": best.setup_name if best and best.action != "WAIT" else None,
                "best_action": best.action if best else "WAIT",
                "status": "LIVE"
            }
            CACHE["last_update"] = time.time()
            CACHE["status"] = "LIVE"
            
        except Exception as e:
            log.error(f"Gateway fetch error: {e}")
            CACHE["status"] = "TIMEOUT"
            
        await asyncio.sleep(2)

async def broadcast_loop():
    """Broadcast current state to all clients every 1s."""
    while True:
        if CACHE["data"]:
            msg = CACHE["data"].copy()
            # Mark data as stale if last update was more than 5s ago
            if CACHE["last_update"] and (time.time() - CACHE["last_update"] > 5):
                msg["status"] = "STALE"
                msg["ts"] = f"{msg['ts']} (STALE)"
            await manager.broadcast(msg)
        await asyncio.sleep(1)

from contextlib import asynccontextmanager
@asynccontextmanager
async def lifespan(app):
    asyncio.create_task(fetch_gateway_data())
    asyncio.create_task(broadcast_loop())
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"])

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # Keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

@app.get("/")
async def health():
    return {"status": CACHE["status"], "clients": len(manager.active_connections), "last_update": CACHE["last_update"]}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8767)
