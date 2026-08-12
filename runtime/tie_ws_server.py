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


@app.get("/api/strategy/status")
def get_strategy_status():
    path = "/home/ubuntu/trading-intelligence-engine/config/strategy_status.json"
    with open(path) as f:
        return json.load(f)


@app.post("/api/strategy/toggle")
def toggle_strategy(payload: dict):
    sid = payload.get("strategy_id")
    enabled = payload.get("enabled")
    path = "/home/ubuntu/trading-intelligence-engine/config/strategy_status.json"
    with open(path) as f:
        data = json.load(f)
    if sid in data:
        data[sid] = enabled
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
        return {"status": "ok"}
    return {"error": "Not found"}


@app.get("/api/features/status")
def get_features():
    path = "/home/ubuntu/trading-intelligence-engine/config/features.json"
    with open(path) as f:
        return json.load(f)


@app.post("/api/features/toggle")
def toggle_feature(payload: dict):
    feat = payload.get("feature_id")
    enabled = payload.get("enabled")
    path = "/home/ubuntu/trading-intelligence-engine/config/features.json"
    with open(path) as f:
        data = json.load(f)
    if feat in data:
        data[feat] = enabled
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
        return {"status": "ok"}
    return {"error": "Not found"}


@app.post("/api/engine/start")
def engine_start():
    """Start TIE production engine via systemctl."""
    import subprocess
    try:
        subprocess.run(["sudo", "systemctl", "start", "tie-production.service"], check=True, timeout=5)
        return {"status": "ok", "message": "Engine started"}
    except Exception as e:
        log.error(f"engine/start failed: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/api/engine/stop")
def engine_stop():
    """Stop TIE production engine via systemctl."""
    import subprocess
    try:
        subprocess.run(["sudo", "systemctl", "stop", "tie-production.service"], check=True, timeout=5)
        return {"status": "ok", "message": "Engine stopped"}
    except Exception as e:
        log.error(f"engine/stop failed: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/api/engine/restart")
def engine_restart():
    """Restart TIE production engine via systemctl."""
    import subprocess
    try:
        subprocess.run(["sudo", "systemctl", "restart", "tie-production.service"], check=True, timeout=10)
        return {"status": "ok", "message": "Engine restarted"}
    except Exception as e:
        log.error(f"engine/restart failed: {e}")
        return {"status": "error", "message": str(e)}


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
  --up: #3fb950; --down: #f85149; --sidebar: #0d1117;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { 
  background: var(--bg); 
  color: var(--text); 
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  display: flex;
  min-height: 100vh;
}

/* Sidebar */
.sidebar {
  width: 240px;
  background: var(--sidebar);
  border-right: 1px solid var(--border);
  padding: 20px 0;
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  overflow-y: auto;
}
.sidebar-header {
  padding: 0 20px 20px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 10px;
}
.sidebar-title {
  color: var(--accent);
  font-size: 16px;
  font-weight: 600;
}
.sidebar-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}
.nav-section {
  padding: 10px 0;
}
.nav-title {
  font-size: 10px;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 1px;
  padding: 8px 20px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  color: var(--text);
  cursor: pointer;
  transition: background 0.2s;
  font-size: 13px;
}
.nav-item:hover { background: rgba(255,255,255,0.05); }
.nav-item.active { background: rgba(0,255,136,0.1); color: var(--accent); border-left: 3px solid var(--accent); }

/* Main Content */
.main {
  flex: 1;
  margin-left: 240px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.main-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.clock { color: var(--muted); font-size: 12px; }

/* Cards */
.card { 
  background: var(--card); 
  border: 1px solid var(--border); 
  border-radius: 8px; 
  padding: 16px;
}
.card-title { 
  font-size: 11px; 
  font-weight: 600; 
  color: var(--muted); 
  text-transform: uppercase; 
  letter-spacing: 1px; 
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th { color: var(--muted); font-weight: normal; text-align: left; padding: 8px; border-bottom: 1px solid var(--border); }
td { padding: 10px 8px; border-bottom: 1px solid #21262d; }
.up { color: var(--up); } .down { color: var(--down); } .accent { color: var(--accent); }
.badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 10px; font-weight: bold; }
.badge-live { background: rgba(63,185,80,.15); color: var(--up); }
.badge-wait { background: rgba(139,148,158,.1); color: var(--muted); }
.badge-err { background: rgba(248,81,73,.15); color: var(--down); }

/* Sidebar mini cards */
.sidebar-card {
  background: rgba(255,255,255,0.03);
  border-radius: 6px;
  padding: 12px;
  margin: 0 12px 12px;
}
.sidebar-kv {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding: 4px 0;
}
.sidebar-kv-label { color: var(--muted); }
</style>
</head>
<body>

<!-- Sidebar -->
<aside class="sidebar">
  <div class="sidebar-header">
    <div class="sidebar-title">TIE v3 Terminal</div>
    <div class="sidebar-status">
      <span id="status-badge" class="badge">—</span>
      <span id="clock" class="clock"></span>
    </div>
  </div>
  
  <nav class="nav-section">
    <div class="nav-title">Strategies</div>
    <div id="strategy-toggles" style="padding:0 20px"></div>
  </nav>

  <nav class="nav-section">
    <div class="nav-title">Feature Toggles</div>
    <div id="feature-toggles" style="padding:0 20px"></div>
  </nav>

  <nav class="nav-section">
    <div class="nav-title">Markets</div>
    <div id="nav-markets"></div>
  </nav>
  
  <nav class="nav-section">
    <div class="nav-title">Account</div>
    <div class="sidebar-card" id="sidebar-acct">
      <div class="sidebar-kv"><span class="sidebar-kv-label">Balance</span><span id="acct-balance">—</span></div>
      <div class="sidebar-kv"><span class="sidebar-kv-label">Equity</span><span id="acct-equity">—</span></div>
      <div class="sidebar-kv"><span class="sidebar-kv-label">Floating</span><span id="acct-pnl">—</span></div>
    </div>
  </nav>
  
  <nav class="nav-section">
    <div class="nav-title">System</div>
    <div class="nav-item"><span>⚙️</span> Settings</div>
    <div class="nav-item"><span>📊</span> Logs</div>
  </nav>
</aside>

<!-- Main Content -->
<main class="main">
  <div class="main-header">
    <div></div>
    <div id="last-scan" style="color:var(--muted);font-size:11px;">Last scan: —</div>
  </div>
  
  <!-- Open Positions -->
  <div class="card">
    <div class="card-title">📈 Open Positions</div>
    <table>
      <thead><tr><th>Symbol</th><th>Dir</th><th>Vol</th><th>Entry</th><th>SL</th><th>TP</th><th>PnL</th></tr></thead>
      <tbody id="pos-body"><tr><td colspan="7" style="color:var(--muted);text-align:center">No open positions</td></tr></tbody>
    </table>
  </div>
  
  <!-- Setup Approved -->
  <div class="card">
    <div class="card-title">✅ Setup Approved (Ready to Execute)</div>
    <table>
      <thead><tr><th>Symbol</th><th>Strategy</th><th>Setup</th><th>Dir</th><th>Conf</th><th>Entry</th><th>SL</th><th>TP</th><th>RR</th></tr></thead>
      <tbody id="sig-approved"><tr><td colspan="9" style="color:var(--muted);text-align:center">No approved signals</td></tr></tbody>
    </table>
  </div>
  
  <!-- Setup Blocked -->
  <div class="card">
    <div class="card-title">❌ Setup Blocked (Risk Gate Reject)</div>
    <table>
      <thead><tr><th>Symbol</th><th>Strategy</th><th>Setup</th><th>Dir</th><th>Conf</th><th>Reason</th></tr></thead>
      <tbody id="sig-blocked"><tr><td colspan="6" style="color:var(--muted);text-align:center">No blocked signals</td></tr></tbody>
    </table>
  </div>
</main>

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
    document.getElementById('acct-equity').textContent = '$' + fmt(d.equity ?? ai.equity);
    const pnl = d.floating_pnl ?? 0;
    const pnlEl = document.getElementById('acct-pnl');
    pnlEl.textContent = (pnl >= 0 ? '+' : '') + fmt(pnl);
    pnlEl.className = pnl >= 0 ? 'up' : 'down';
    document.getElementById('last-scan').textContent = 'Last scan: ' + ts(d.ts);
    
    // Sidebar markets
    const syms = d.symbols_data || d.pairs || {};
    const navMarkets = document.getElementById('nav-markets');
    navMarkets.innerHTML = Object.entries(syms).map(([sym, v]) => {
      const closed = !v.price;
      const badgeClass = closed ? 'badge-wait' : 'badge-live';
      const badgeText = closed ? 'CLOSED' : 'LIVE';
      return `<div class="nav-item">
        <span>${closed ? '💤' : '📊'}</span>
        <span>${sym}</span>
        <span class="badge ${badgeClass}" style="margin-left:auto">${badgeText}</span>
      </div>`;
    }).join('') || '<div class="nav-item" style="color:var(--muted)">No data</div>';
    
    // Positions
    const positions = d.positions || [];
    const posBody = document.getElementById('pos-body');
    if (positions.length) {
      posBody.innerHTML = positions.map(p => `<tr>
        <td class="accent">${p.symbol||'—'}</td>
        <td class="${dirClass(p.side)}">${(p.side||'').toUpperCase()}</td>
        <td>${fmt(p.volume,2)}</td>
        <td>${fmt(p.entry, p.symbol==='BTCUSD'?2:5)}</td>
        <td style="color:var(--down)">${fmt(p.sl, p.symbol==='BTCUSD'?2:5)}</td>
        <td style="color:var(--up)">${fmt(p.tp, p.symbol==='BTCUSD'?2:5)}</td>
        <td class="${(p.pnl||0)>=0?'up':'down'}">${fmt(p.pnl,2)}</td>
      </tr>`).join('');
    } else {
      posBody.innerHTML = '<tr><td colspan="7" style="color:var(--muted);text-align:center">No open positions</td></tr>';
    }
    
    // Signals — split into Approved vs Blocked
    const approvedBody = document.getElementById('sig-approved');
    const blockedBody = document.getElementById('sig-blocked');
    const approved = [];
    const blocked = [];
    
    Object.entries(syms).forEach(([sym, v]) => {
      if (v.setup) {
        const s = v.setup;
        if (s.status === 'APPROVED') {
          approved.push({sym, ...s});
        } else if (s.status === 'BLOCKED' || s.status === 'DEDUP') {
          blocked.push({sym, ...s});
        }
      }
    });
    
    // Approved signals
    if (approved.length) {
      approvedBody.innerHTML = approved.map(s => `<tr>
        <td class="accent">${s.sym}</td>
        <td>${s.strategy||'—'}</td>
        <td>${s.setup_name||'—'}</td>
        <td class="${dirClass(s.direction)}">${(s.direction||'').toUpperCase()}</td>
        <td class="accent">${s.confidence?s.confidence.toFixed(0)+'%':'—'}</td>
        <td>${fmt(s.entry, s.sym==='BTCUSD'?2:5)}</td>
        <td style="color:var(--down)">${fmt(s.sl, s.sym==='BTCUSD'?2:5)}</td>
        <td style="color:var(--up)">${fmt(s.tp, s.sym==='BTCUSD'?2:5)}</td>
        <td>${fmt(s.risk_reward,2)}</td>
      </tr>`).join('');
    } else {
      approvedBody.innerHTML = '<tr><td colspan="9" style="color:var(--muted);text-align:center">No approved signals</td></tr>';
    }
    
    // Blocked signals
    if (blocked.length) {
      blockedBody.innerHTML = blocked.map(s => `<tr>
        <td class="accent">${s.sym}</td>
        <td>${s.strategy||'—'}</td>
        <td>${s.setup_name||'—'}</td>
        <td class="${dirClass(s.direction)}">${(s.direction||'').toUpperCase()}</td>
        <td class="accent">${s.confidence?s.confidence.toFixed(0)+'%':'—'}</td>
        <td style="color:var(--down);font-size:11px">${s.gate_reason||'Unknown'}</td>
      </tr>`).join('');
    } else {
      blockedBody.innerHTML = '<tr><td colspan="6" style="color:var(--muted);text-align:center">No blocked signals</td></tr>';
    }
  }).catch(e => console.error('Poll failed:', e));
}

setInterval(updateUI, 2000);
setInterval(() => { document.getElementById('clock').textContent = new Date().toLocaleTimeString(); }, 1000);
const statusBadge = document.getElementById('status-badge');
      
// Inject strategies from status file
fetch('/api/strategy/status').then(r => r.json()).then(d => {
  const cont = document.getElementById('strategy-toggles');
  const labels = {bystra_v1: 'Bystra', aggressive_v1: 'Aggressive', semi_hft_c8: 'SemiHFT'};
  Object.entries(d).forEach(([sid, enabled]) => {
    cont.innerHTML += `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;padding:4px 0;border-bottom:1px solid #30363d">
      <span style="font-size:12px;color:${enabled?'#00ff88':'#8b949e'}">${labels[sid]||sid}</span>
      <label style="position:relative;display:inline-block;width:32px;height:18px">
        <input type="checkbox" ${enabled?'checked':''} style="opacity:0;width:0;height:0" 
          onchange="fetch('/api/strategy/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({strategy_id:'${sid}',enabled:this.checked})}).then(()=>location.reload())">
        <span style="position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;background:${enabled?'#00ff88':'#30363d'};border-radius:18px;transition:.3s"></span>
      </label>
    </div>`;
  });
}).catch(() => {
  document.getElementById('strategy-toggles').innerHTML = '<span style="font-size:11px;color:#8b949e">Status unavailable</span>';
});

// Inject feature toggles
fetch('/api/features/status').then(r => r.json()).then(d => {
  const cont = document.getElementById('feature-toggles');
  const labels = {volatility_sizing: 'Volatility Sizing', zscore_filter: 'Z-Score Filter', mean_reversion_filter: 'Mean Reversion', auto_allocation: 'Auto Allocation'};
  Object.entries(d).forEach(([fid, enabled]) => {
    if (typeof enabled !== 'boolean') return;
    cont.innerHTML += `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;padding:4px 0;border-bottom:1px solid #30363d">
      <span style="font-size:12px;color:${enabled?'#00ff88':'#8b949e'}">${labels[fid]||fid}</span>
      <label style="position:relative;display:inline-block;width:32px;height:18px">
        <input type="checkbox" ${enabled?'checked':''} style="opacity:0;width:0;height:0" 
          onchange="fetch('/api/features/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({feature_id:'${fid}',enabled:this.checked})}).then(()=>location.reload())">
        <span style="position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;background:${enabled?'#00ff88':'#30363d'};border-radius:18px;transition:.3s"></span>
      </label>
    </div>`;
  });
}).catch(() => {
  document.getElementById('feature-toggles').innerHTML = '<span style="font-size:11px;color:#8b949e">Status unavailable</span>';
});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3002)
