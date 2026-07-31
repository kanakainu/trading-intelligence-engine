#!/usr/bin/env python3
"""TIE v2 Trading Dashboard — Dark Theme, Modern UI."""
import asyncio, json, logging, sys, time
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

sys.path.insert(0, '/home/ubuntu/.hermes/trading')
sys.path.insert(0, '/home/ubuntu/trading-intelligence-engine')

from gateway_client import MT5GatewayClient
from core.context.context_model import MarketContext
from strategy.orchestrator import StrategyOrchestrator
from detectors.common import find_nearest_support, find_nearest_resistance
from runtime.entry_monitor import EntryMonitor

logging.basicConfig(level=logging.INFO, format='%(asctime)s TIE_WS %(message)s')
log = logging.getLogger("TIE_WS")

URL = 'https://chips-extension-extensions-wearing.trycloudflare.com'
TOKEN = 'Jojo_56790@_000tUi_OO9'
SYMBOLS = ['XAUUSD', 'BTCUSD', 'GBPJPY']

# Global State
client = MT5GatewayClient(URL, TOKEN, timeout=5)
orc = StrategyOrchestrator(min_confidence=0.50)
entry_monitor = EntryMonitor(broker=None, gateway=client)
CACHE = {
    "status": "INITIALIZING",
    "last_scan_time": None,
    "symbols_data": {sym: {} for sym in SYMBOLS},
    "account_info": {},
    "positions": [],
    "entry_monitor_status": "Idle"
}

async def fetch_gateway_data():
    """Background task to fetch data from MT5 Gateway."""
    loop = asyncio.get_event_loop()
    while True:
        try:
            account_info_task = loop.run_in_executor(None, client.account)
            positions_task = loop.run_in_executor(None, client.positions)
            account, all_positions = await asyncio.gather(account_info_task, positions_task)

            CACHE["account_info"] = account or {}
            CACHE["positions"] = all_positions or []

            for sym in SYMBOLS:
                tasks = [
                    loop.run_in_executor(None, client.candles, sym, "M5", 50),
                    loop.run_in_executor(None, client.candles, sym, "M15", 30),
                    loop.run_in_executor(None, client.candles, sym, "H1", 20),
                    loop.run_in_executor(None, client.price, sym),
                ]
                m5, m15, h1, price_data = await asyncio.gather(*tasks)
                
                price = price_data['ask']
                spread = round(price_data.get("spread", 0), 2)
                sup = find_nearest_support(h1, price)
                res = find_nearest_resistance(h1, price)
                
                ctx = MarketContext(symbol=sym, timestamp=datetime.now(timezone.utc))
                ctx.metadata.update({
                    "candles": {"M5": m5, "M15": m15, "H1": h1},
                    "current_price": price,
                    "h1_support": sup, "h1_resistance": res,
                    "h1_trend": "bullish" if h1 and len(h1) >= 5 and h1[-1]['close'] > h1[-5]['close'] else "bearish",
                    "nearest_support": sup, "nearest_resistance": res,
                    "atr": 5.0,
                    "spread": spread,
                })
                
                facts = orc.run(ctx)
                best = orc.best_decision(ctx)
                
                CACHE["symbols_data"][sym] = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "price": round(price, 5),
                    "spread": spread,
                    "support": round(sup, 2) if sup else 0,
                    "resistance": round(res, 2) if res and res < 999999 else 0,
                    "trend": ctx.metadata["h1_trend"],
                    "setups": [{
                        "name": f.value,
                        "direction": f.metadata.get("direction", "?"),
                        "confidence": round(f.confidence, 2),
                        "sl": round(f.metadata.get("sl", 0), 2),
                        "tp": round(f.metadata.get("tp", 0), 2),
                    } for f in sorted(facts, key=lambda x: -x.confidence)],
                    "best_setup": best.setup_name if best and best.action != "WAIT" else None,
                    "best_action": best.action if best else "WAIT",
                }

            # Update EntryMonitor status (simplified)
            entry_monitor.tick(CACHE["positions"])
            CACHE["entry_monitor_status"] = "Active" if len(entry_monitor._active_setups) > 0 else "Idle"

            CACHE["last_scan_time"] = datetime.now(timezone.utc).isoformat()
            CACHE["status"] = "LIVE"
            
        except Exception as e:
            log.error(f"Gateway fetch error: {e}")
            CACHE["status"] = "TIMEOUT"
            
        await asyncio.sleep(2)

from contextlib import asynccontextmanager
@asynccontextmanager
async def lifespan(app):
    asyncio.create_task(fetch_gateway_data())
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"])

@app.get("/api/status")
async def get_status():
    return JSONResponse(content=CACHE)

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TIE v2 Trading Terminal</title>
    <style>
        :root {
            --bg-color: #0d1117;
            --card-bg: #161b22;
            --accent-color: #00ff88;
            --text-color: #c9d1d9;
            --text-muted: #8b949e;
            --border-color: #30363d;
            --up-color: #3fb950;
            --down-color: #f85149;
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 20px;
        }
        .dashboard {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            grid-gap: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .card {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 15px;
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
        }
        .card-title {
            font-size: 14px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        th, td {
            text-align: left;
            padding: 8px;
            border-bottom: 1px solid var(--border-color);
        }
        th {
            color: var(--text-muted);
            font-weight: normal;
        }
        .accent { color: var(--accent-color); }
        .up { color: var(--up-color); }
        .down { color: var(--down-color); }
        .status-badge {
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
        }
        .status-live { background-color: rgba(63, 185, 80, 0.2); color: var(--up-color); }
        .status-idle { background-color: rgba(139, 148, 158, 0.2); color: var(--text-muted); }
        .status-error { background-color: rgba(248, 81, 73, 0.2); color: var(--down-color); }
    </style>
</head>
<body>
    <div style="display: flex; justify-content: space-between; align-items: center; max-width: 1200px; margin: 0 auto 20px auto;">
        <h1 style="margin: 0; font-size: 20px; font-weight: 400;"><span class="accent">TIE</span> v2 Terminal</h1>
        <div id="system-clock" style="font-size: 14px; color: var(--text-muted);">00:00:00</div>
    </div>

    <div class="dashboard">
        <!-- Market Watch -->
        <div class="card">
            <div class="card-header">
                <div class="card-title">Market Watch</div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Price</th>
                        <th>Spread</th>
                        <th>Trend</th>
                    </tr>
                </thead>
                <tbody id="market-watch">
                </tbody>
            </table>
        </div>

        <!-- System Status -->
        <div class="card">
            <div class="card-header">
                <div class="card-title">System Status</div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); grid-gap: 10px; font-size: 13px;">
                <div>Gateway: <span id="gateway-status" class="status-badge">N/A</span></div>
                <div>EntryMonitor: <span id="entry-monitor-status" class="status-badge">N/A</span></div>
                <div style="grid-column: span 2; margin-top: 5px;">Last Scan: <span id="last-scan" style="color: var(--text-muted);">N/A</span></div>
                <div style="grid-column: span 2;">Balance: <span id="balance" class="accent">$0.00</span> | Equity: <span id="equity" class="accent">$0.00</span></div>
            </div>
        </div>

        <!-- Open Positions -->
        <div class="card" style="grid-column: span 2;">
            <div class="card-header">
                <div class="card-title">Open Positions</div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Side</th>
                        <th>Volume</th>
                        <th>Entry</th>
                        <th>SL / TP</th>
                        <th>PnL</th>
                    </tr>
                </thead>
                <tbody id="open-positions">
                </tbody>
            </table>
        </div>

        <!-- Setup Signals -->
        <div class="card" style="grid-column: span 2;">
            <div class="card-header">
                <div class="card-title">Setup Signals</div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Strategy</th>
                        <th>Conf %</th>
                        <th>Direction</th>
                        <th>Target (SL/TP)</th>
                    </tr>
                </thead>
                <tbody id="setup-signals">
                </tbody>
            </table>
        </div>
    </div>

    <script>
        function updateUI() {
            fetch('/api/status')
                .then(res => res.json())
                .then(data => {
                    // Update System Status
                    const gatewayStatus = document.getElementById('gateway-status');
                    gatewayStatus.textContent = data.status;
                    gatewayStatus.className = 'status-badge ' + (data.status === 'LIVE' ? 'status-live' : 'status-error');

                    const emStatus = document.getElementById('entry-monitor-status');
                    emStatus.textContent = data.entry_monitor_status;
                    emStatus.className = 'status-badge ' + (data.entry_monitor_status === 'Active' ? 'status-live' : 'status-idle');

                    document.getElementById('last-scan').textContent = data.last_scan_time ? new Date(data.last_scan_time).toLocaleTimeString() : 'N/A';
                    document.getElementById('balance').textContent = '$' + (data.account_info.balance || 0).toLocaleString();
                    document.getElementById('equity').textContent = '$' + (data.account_info.equity || 0).toLocaleString();

                    // Update Market Watch
                    const mwBody = document.getElementById('market-watch');
                    mwBody.innerHTML = '';
                    for (const [sym, symData] of Object.entries(data.symbols_data)) {
                        if (!symData.price) continue;
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td style="font-weight: 600;">${sym}</td>
                            <td class="accent">${symData.price.toFixed(sym.includes('JPY') ? 3 : 5)}</td>
                            <td>${symData.spread}</td>
                            <td class="${symData.trend === 'bullish' ? 'up' : 'down'}">${symData.trend.toUpperCase()}</td>
                        `;
                        mwBody.appendChild(tr);
                    }

                    // Update Open Positions
                    const posBody = document.getElementById('open-positions');
                    posBody.innerHTML = '';
                    (data.positions || []).forEach(p => {
                        const tr = document.createElement('tr');
                        const pnl = parseFloat(p.profit || 0);
                        tr.innerHTML = `
                            <td>${p.symbol}</td>
                            <td class="${p.type.includes('BUY') ? 'up' : 'down'}">${p.type}</td>
                            <td>${p.volume}</td>
                            <td>${p.price_open}</td>
                            <td style="font-size: 11px; color: var(--text-muted);">${p.sl} / ${p.tp}</td>
                            <td class="${pnl >= 0 ? 'up' : 'down'}" style="font-weight: 600;">${pnl.toFixed(2)}</td>
                        `;
                        posBody.appendChild(tr);
                    });
                    if (data.positions.length === 0) {
                        posBody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">No open positions</td></tr>';
                    }

                    // Update Setup Signals
                    const sigBody = document.getElementById('setup-signals');
                    sigBody.innerHTML = '';
                    let hasSignals = false;
                    for (const [sym, symData] of Object.entries(data.symbols_data)) {
                        (symData.setups || []).forEach(s => {
                            hasSignals = true;
                            const tr = document.createElement('tr');
                            tr.innerHTML = `
                                <td>${sym}</td>
                                <td>${s.name}</td>
                                <td class="accent">${(s.confidence * 100).toFixed(0)}%</td>
                                <td class="${s.direction === 'BUY' ? 'up' : 'down'}">${s.direction}</td>
                                <td style="font-size: 11px; color: var(--text-muted);">${s.sl} / ${s.tp}</td>
                            `;
                            sigBody.appendChild(tr);
                        });
                    }
                    if (!hasSignals) {
                        sigBody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No active signals</td></tr>';
                    }
                })
                .catch(err => console.error('Status fetch failed:', err));
        }

        setInterval(updateUI, 2000);
        setInterval(() => {
            document.getElementById('system-clock').textContent = new Date().toLocaleTimeString();
        }, 1000);
        updateUI();
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3001)
