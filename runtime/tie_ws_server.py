#!/usr/bin/env python3
"""TIE v3 Dashboard — reads tie_status.json written by tie_production.py.
No strategy computation here. Single source of truth = production process.
"""
import json, logging, os, sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

logging.basicConfig(level=logging.INFO, format='%(asctime)s TIE_DASH %(message)s')
log = logging.getLogger("TIE_DASH")

STATUS_PATH = "/home/ubuntu/tie-dashboard/data/tie_status.json"

def read_status() -> dict:
    try:
        with open(STATUS_PATH) as f:
            data = json.load(f)
        data["status"] = "LIVE"
        # Normalise symbols_data from 'pairs' key written by tie_production
        if "pairs" in data and "symbols_data" not in data:
            data["symbols_data"] = data["pairs"]
        return data
    except FileNotFoundError:
        return {"status": "WAITING", "symbols_data": {}, "positions": [], "account_info": {}}
    except Exception as e:
        log.warning("read_status failed: %s", e)
        return {"status": "ERROR", "error": str(e), "symbols_data": {}, "positions": []}


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("TIE Dashboard v3 started — reading %s", STATUS_PATH)
    yield
    log.info("TIE Dashboard v3 stopped.")

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/status")
def api_status():
    return JSONResponse(read_status())


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse(content=HTML)


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TIE v3 Trading Terminal</title>
<style>
:root {
  --bg: #0d1117; --card: #161b22; --accent: #00ff88;
  --text: #c9d1d9; --muted: #8b949e; --border: #30363d;
  --up: #3fb950; --down: #f85149;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; padding: 16px; }
h1 { color: var(--accent); font-size: 18px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
.card-title { font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th { color: var(--muted); font-weight: normal; text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); }
td { padding: 8px; border-bottom: 1px solid #21262d; }
.up { color: var(--up); } .down { color: var(--down); } .accent { color: var(--accent); }
.badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: bold; }
.badge-live { background: rgba(63,185,80,.15); color: var(--up); }
.badge-wait { background: rgba(139,148,158,.1); color: var(--muted); }
.badge-err  { background: rgba(248,81,73,.15); color: var(--down); }
.kv { display: flex; justify-content: space-between; padding: 4px 0; font-size: 12px; border-bottom: 1px solid #21262d; }
.kv:last-child { border-bottom: none; }
.kv-label { color: var(--muted); }
#clock { color: var(--muted); font-size: 12px; }
#status-badge { margin-left: 8px; }
</style>
</head>
<body>
<h1>
  TIE v3 Terminal
  <span>
    <span id="status-badge" class="badge">—</span>
    &nbsp;<span id="clock"></span>
  </span>
</h1>

<div class="grid">
  <!-- Market Watch -->
  <div class="card">
    <div class="card-title">Market Watch</div>
    <table>
      <thead><tr><th>Symbol</th><th>Price</th><th>Spread</th><th>Trend</th><th>Status</th></tr></thead>
      <tbody id="mw-body"><tr><td colspan="5" style="color:var(--muted);text-align:center">Loading…</td></tr></tbody>
    </table>
  </div>

  <!-- Account -->
  <div class="card">
    <div class="card-title">Account</div>
    <div id="acct-body">
      <div class="kv"><span class="kv-label">Balance</span><span id="acct-balance">—</span></div>
      <div class="kv"><span class="kv-label">Equity</span><span id="acct-equity">—</span></div>
      <div class="kv"><span class="kv-label">Floating PnL</span><span id="acct-pnl">—</span></div>
      <div class="kv"><span class="kv-label">Last Scan</span><span id="last-scan">—</span></div>
    </div>
  </div>

  <!-- Open Positions -->
  <div class="card">
    <div class="card-title">Open Positions</div>
    <table>
      <thead><tr><th>Symbol</th><th>Dir</th><th>Vol</th><th>Entry</th><th>PnL</th></tr></thead>
      <tbody id="pos-body"><tr><td colspan="5" style="color:var(--muted);text-align:center">No open positions</td></tr></tbody>
    </table>
  </div>

  <!-- Setup Signals -->
  <div class="card">
    <div class="card-title">Setup Signals</div>
    <table>
      <thead><tr><th>Symbol</th><th>Setup</th><th>Dir</th><th>Conf</th><th>SL/TP</th></tr></thead>
      <tbody id="sig-body"><tr><td colspan="5" style="color:var(--muted);text-align:center">No active signals</td></tr></tbody>
    </table>
  </div>
</div>

<script>
function fmt(n, dec=2) { return n != null ? (+n).toFixed(dec) : '—'; }
function dirClass(d) { return (d||'').toUpperCase()==='BUY'?'up':'down'; }
function ts(iso) { return iso ? new Date(iso).toLocaleTimeString() : '—'; }

function updateUI() {
  fetch('/api/status').then(r => r.json()).then(d => {
    // Badge
    const badge = document.getElementById('status-badge');
    badge.textContent = d.status || '—';
    badge.className = 'badge badge-' + (d.status==='LIVE'?'live': d.status==='ERROR'?'err':'wait');

    // Account
    const ai = d.account_info || {};
    document.getElementById('acct-balance').textContent = '$' + fmt(d.balance ?? ai.balance);
    document.getElementById('acct-equity').textContent  = '$' + fmt(d.equity  ?? ai.equity);
    const pnl = d.floating_pnl ?? 0;
    const pnlEl = document.getElementById('acct-pnl');
    pnlEl.textContent = (pnl >= 0 ? '+' : '') + fmt(pnl);
    pnlEl.className = pnl >= 0 ? 'up' : 'down';
    document.getElementById('last-scan').textContent = ts(d.ts);

    // Market Watch
    const syms = d.symbols_data || d.pairs || {};
    const mwBody = document.getElementById('mw-body');
    const mwRows = Object.entries(syms).map(([sym, v]) => {
      const closed = !v.price;
      const statusBadge = closed
        ? '<span class="badge badge-wait">CLOSED</span>'
        : '<span class="badge badge-live">LIVE</span>';
      return `<tr>
        <td class="accent">${sym}</td>
        <td>${v.price ? fmt(v.price, sym==='BTCUSD'?2:5) : '—'}</td>
        <td>${v.spread || '—'}</td>
        <td class="${(v.trend||'').includes('bull')?'up':'down'}">${v.trend||'—'}</td>
        <td>${statusBadge}</td>
      </tr>`;
    }).join('');
    mwBody.innerHTML = mwRows || '<tr><td colspan="5" style="color:var(--muted);text-align:center">No data</td></tr>';

    // Positions
    const positions = d.positions || [];
    const posBody = document.getElementById('pos-body');
    if (positions.length) {
      posBody.innerHTML = positions.map(p => `<tr>
        <td class="accent">${p.symbol||'—'}</td>
        <td class="${dirClass(p.side)}">${(p.side||'').toUpperCase()}</td>
        <td>${fmt(p.volume,2)}</td>
        <td>${fmt(p.entry,2)}</td>
        <td class="${(p.pnl||0)>=0?'up':'down'}">${fmt(p.pnl,2)}</td>
      </tr>`).join('');
    } else {
      posBody.innerHTML = '<tr><td colspan="5" style="color:var(--muted);text-align:center">No open positions</td></tr>';
    }

    // Signals — iterate symbols_data for setups
    const sigBody = document.getElementById('sig-body');
    const sigs = [];
    Object.entries(syms).forEach(([sym, v]) => {
      if (v.setup) sigs.push({sym, ...v.setup});
    });
    if (sigs.length) {
      sigBody.innerHTML = sigs.map(s => `<tr>
        <td class="accent">${s.sym}</td>
        <td>${s.name||'—'}</td>
        <td class="${dirClass(s.direction)}">${(s.direction||'').toUpperCase()}</td>
        <td class="accent">${s.confidence ? (s.confidence*100).toFixed(0)+'%' : '—'}</td>
        <td style="font-size:11px;color:var(--muted)">${fmt(s.sl,2)} / ${fmt(s.tp||s.take_profit,2)}</td>
      </tr>`).join('');
    } else {
      sigBody.innerHTML = '<tr><td colspan="5" style="color:var(--muted);text-align:center">No active signals</td></tr>';
    }
  }).catch(e => console.error('Poll failed:', e));
}

setInterval(updateUI, 2000);
setInterval(() => { document.getElementById('clock').textContent = new Date().toLocaleTimeString(); }, 1000);
updateUI();
</script>
</body>
</html>"""


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3001)
