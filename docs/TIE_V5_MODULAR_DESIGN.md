# TIE V5 — Modular Standalone Engine
**Status:** DESIGN PLAN (belum implement)
**Date:** 2026-08-06
**Goal:** TIE V4 jadi 1 folder portable, jalan di Windows (bareng MT5) atau Linux (via gateway).

---

## 1. Problem Statement

TIE V4 saat ini:
- 3172 files, tersebar di 29+ directories
- Hardcoded Linux paths (`/home/ubuntu/...`, `/tmp/...`)
- Depends on systemd, Cloudflare tunnel, external gateway process
- MT5 connection via HTTP gateway (extra layer = extra fragility)
- Tidak bisa dipindah ke Windows tanpa rewrite besar
- Config tersebar: hardcoded di source code (THRESHOLD=60, daily_target=30, dll)

**Target:** 1 folder `tie-v5/` yang bisa di-copy ke Windows VPS + run bareng MT5.

---

## 2. Target Folder Structure

```
tie-v5/
├── run.py                    # Single entry point
├── config.yaml               # ALL config di 1 file
├── requirements.txt          # Dependencies
├── README.md                 # Setup guide
│
├── core/                     # Pipeline engine (platform-agnostic)
│   ├── __init__.py
│   ├── pipeline.py           # Main scan loop (10s cycle)
│   ├── context.py            # MarketContext builder
│   ├── signals.py            # Signal/TradePlan models
│   └── state.py              # Runtime state (day_start, equity, positions)
│
├── adapters/                 # Platform-specific I/O
│   ├── __init__.py
│   ├── broker.py             # Abstract broker interface
│   ├── mt5_direct.py         # Windows: MetaTrader5 Python package
│   ├── mt5_gateway.py        # Linux: HTTP gateway (current method)
│   └── data_feed.py          # Candle/tick data abstraction
│
├── strategies/               # Strategy plugins (drop-in)
│   ├── __init__.py
│   ├── registry.py           # Auto-discover strategies in this dir
│   ├── base.py               # BaseStrategy ABC
│   ├── bystra/
│   │   ├── __init__.py
│   │   ├── strategy.py
│   │   └── detectors/        # 14 detectors
│   ├── aggressive/
│   │   ├── __init__.py
│   │   ├── strategy.py
│   │   ├── engines/          # momentum, velocity, microstructure, dll
│   │   └── detectors/
│   └── semi_hft/
│       ├── __init__.py
│       ├── strategy.py
│       └── engines/          # tick_velocity, volatility, recovery, dll
│
├── risk/                     # Risk management (platform-agnostic)
│   ├── __init__.py
│   ├── gate.py               # RiskGate (mandate, SL/TP validation, session)
│   ├── position_sizer.py     # Dynamic lot calculation
│   ├── trailing.py           # TrailingManager + BE lock
│   └── governor.py           # Daily profit/loss governor
│
├── exit/                     # Exit logic
│   ├── __init__.py
│   ├── orchestrator.py       # ExitOrchestrator (adaptive RR, trailing config)
│   └── executor.py           # ContractExecutor (BE, partial TP, early exit)
│
├── monitor/                  # Position monitoring
│   ├── __init__.py
│   ├── position_monitor.py   # Watch open positions, trigger exits
│   └── outcome_tracker.py    # Win/loss tracking
│
├── features/                 # Feature engineering
│   ├── __init__.py
│   ├── engine.py             # FeatureEngine (indicators, patterns)
│   └── models.py             # FeatureSnapshot dataclass
│
├── dashboard/                # Optional web dashboard
│   ├── __init__.py
│   ├── server.py             # FastAPI backend (port configurable)
│   └── static/               # Frontend HTML/JS/CSS
│
├── data/                     # Runtime data (created automatically)
│   ├── day_start.json        # Day-start balance (persistent)
│   ├── state.json            # Engine state snapshot
│   └── trades.json           # Trade log
│
└── logs/                     # Log files (created automatically)
    └── tie.log
```

---

## 3. Key Design Decisions

### 3.1 Broker Adapter Pattern
```python
# adapters/broker.py — Abstract interface
class BrokerAdapter(ABC):
    def account(self) -> AccountInfo: ...
    def positions(self) -> list[Position]: ...
    def candles(self, symbol, tf, count) -> list[Candle]: ...
    def submit_order(self, req: OrderRequest) -> OrderResult: ...
    def modify_order(self, ticket, sl, tp) -> bool: ...
    def close_position(self, ticket) -> bool: ...

# Windows: langsung MetaTrader5 package
class MT5DirectAdapter(BrokerAdapter):
    """Uses `import MetaTrader5 as mt5` — zero gateway needed."""
    
# Linux: HTTP gateway (current method, tetap supported)
class MT5GatewayAdapter(BrokerAdapter):
    """Uses HTTP requests to gateway process."""
```

**Benefit di Windows:** Engine jalan di mesin yang sama dengan MT5. Tidak perlu gateway, tidak perlu Cloudflare tunnel. Latency lebih rendah, satu less point of failure.

### 3.2 Single Config File
```yaml
# config.yaml — SATU sumber kebenaran
broker:
  type: "mt5_direct"          # atau "mt5_gateway"
  mt5_direct:
    login: 12345678
    password: "xxx"
    server: "Exness-MT5Trial14"
    path: "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
  mt5_gateway:
    url: "https://your-tunnel.trycloudflare.com"
    token: "your-token"

trading:
  symbols: ["XAUUSD"]
  default_lot: 0.01
  max_lot: 0.01
  daily_target: 30.0
  daily_loss_limit: 50.0
  scan_interval: 10

strategies:
  bystra:
    enabled: true
    weight: 0.4
  aggressive:
    enabled: true
    weight: 0.3
    threshold: 60.0
  semi_hft:
    enabled: true
    weight: 0.3
    threshold: 60.0

risk:
  max_positions: 3
  min_confidence: 0.60
  allowed_sessions: ["LONDON", "NEW_YORK", "OVERLAP", "ASIA"]

trailing:
  be_trigger_atr: 0.5
  trail_trigger_atr: 1.0
  trail_offset_atr: 0.3

dashboard:
  enabled: true
  port: 3002
```

### 3.3 run.py — Single Entry Point
```python
"""TIE V5 — Single entry point."""
import yaml, sys, logging
from core.pipeline import TradingPipeline
from adapters import create_broker  # factory from config

def main():
    config = yaml.safe_load(open("config.yaml"))
    broker = create_broker(config["broker"])
    pipeline = TradingPipeline(broker, config)
    
    logging.basicConfig(
        filename="logs/tie.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )
    
    pipeline.run()  # blocks, 10s loop

if __name__ == "__main__":
    main()
```

### 3.4 Windows Service (replaces systemd)
```python
# install_service.py — Register as Windows Service
# Uses pywin32 (already needed for MetaTrader5 package)
# Alternative: Task Scheduler (simpler, no extra dep)
```

**Option A (simple):** Task Scheduler → `python run.py` on login
**Option B (production):** NSSM (Non-Sucking Service Manager) → wrap as Windows Service
**Option C (code):** pywin32 `win32serviceutil` → proper Windows Service class

Recommendation: Option B (NSSM). Zero code change, production-grade.

---

## 4. Migration Path (V4 → V5)

### Phase 1: Extract & Clean (1-2 hari)
1. Copy production files dari V4 ke V5 structure
2. Remove hardcoded paths → use `config.yaml` + `pathlib`
3. Remove systemd-specific code → generic process management
4. Consolidate duplicate trailing systems → single `risk/trailing.py`

### Phase 2: Broker Abstraction (1 hari)
1. Create `BrokerAdapter` ABC
2. Wrap current gateway client → `MT5GatewayAdapter`
3. Create `MT5DirectAdapter` using `MetaTrader5` Python package
4. Test both adapters on Linux (gateway) + Windows (direct)

### Phase 3: Config Centralization (0.5 hari)
1. Extract ALL hardcoded values to `config.yaml`
2. Values to extract: THRESHOLD, MIN_ENTRY_SCORE, DEDUP_WINDOW, daily_target, lot tiers, session lists, trailing params, weights
3. Add env var override: `TIE_DAILY_TARGET=50 python run.py`

### Phase 4: Dashboard Portability (0.5 hari)
1. Dashboard reads from `data/state.json` (written by engine)
2. Remove gateway-specific dashboard code
3. Dashboard optional (can disable in config)

### Phase 5: Testing & Documentation (1 hari)
1. Test on Linux VPS (gateway mode) — parity check
2. Test on Windows + MT5 (direct mode)
3. README.md: setup guide for both platforms
4. `requirements.txt`: platform-conditional deps

---

## 5. Dependency Map

```
requirements.txt:
  pyyaml>=6.0
  fastapi>=0.100     # dashboard only
  uvicorn>=0.23      # dashboard only
  
  # Windows only (conditional)
  MetaTrader5>=5.0.45; sys_platform == "win32"
  
  # Linux only (current gateway, no extra dep)
  # uses stdlib urllib
```

---

## 6. Deployment Scenarios

### Scenario A: Windows VPS + MT5 (TARGET)
```
1. Copy tie-v5/ to Windows VPS
2. pip install -r requirements.txt
3. Edit config.yaml (MT5 credentials, set broker.type=mt5_direct)
4. python run.py
5. (Optional) NSSM install as Windows Service
```

### Scenario B: Linux VPS (CURRENT — backward compatible)
```
1. Copy tie-v5/ to Linux VPS
2. pip install -r requirements.txt
3. Edit config.yaml (set broker.type=mt5_gateway, gateway URL)
4. python run.py
5. (Optional) systemd service file
```

### Scenario C: Local Dev (testing)
```
1. Clone repo
2. pip install -r requirements.txt
3. Edit config.yaml (set broker.type=mt5_gateway, test account)
4. python run.py
```

---

## 7. What Gets REMOVED from V4

| Removed | Reason |
|---------|--------|
| `/tmp/` paths | Not portable, cleared on reboot |
| systemd deps | Windows doesn't have systemd |
| Cloudflare tunnel | Not needed when MT5 local |
| Hardcoded thresholds | Moved to config.yaml |
| Duplicate trailing (3 systems) | Consolidated to 1 |
| Manual trailing v2 | Merged into main trailing |
| PID file management | OS-agnostic process handling |
| 29 top-level directories | Reduced to 10 |

---

## 8. What STAYS from V4

| Kept | Reason |
|------|--------|
| Strategy logic (Bystra/Aggressive/SemiHFT) | Core value, ported as-is |
| Detector pipeline | Core value |
| Risk gate logic | Core value |
| Exit orchestrator | Core value |
| Feature engine | Core value |
| All 45 critical fixes | Already battle-tested |

---

## 9. MT5DirectAdapter Sketch

```python
# adapters/mt5_direct.py
import MetaTrader5 as mt5
from adapters.broker import BrokerAdapter, AccountInfo, Position, OrderResult

class MT5DirectAdapter(BrokerAdapter):
    def __init__(self, config: dict):
        mt5.initialize(
            path=config.get("path"),
            login=config["login"],
            password=config["password"],
            server=config["server"],
        )
    
    def account(self) -> AccountInfo:
        info = mt5.account_info()
        return AccountInfo(
            balance=info.balance,
            equity=info.equity,
            margin=info.margin_free,
        )
    
    def positions(self) -> list[Position]:
        return [
            Position(
                ticket=p.ticket,
                symbol=p.symbol,
                direction="buy" if p.type == 0 else "sell",
                volume=p.volume,
                entry=p.price_open,
                sl=p.sl,
                tp=p.tp,
                profit=p.profit,
                comment=p.comment,
            )
            for p in mt5.positions_get()
        ]
    
    def submit_order(self, req) -> OrderResult:
        order = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": req.symbol,
            "volume": req.volume,
            "type": mt5.ORDER_TYPE_BUY if req.direction == "buy" else mt5.ORDER_TYPE_SELL,
            "price": mt5.symbol_info_tick(req.symbol).ask if req.direction == "buy" else mt5.symbol_info_tick(req.symbol).bid,
            "sl": req.sl,
            "tp": req.tp,
            "comment": req.comment,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(order)
        return OrderResult(
            success=result.retcode == mt5.TRADE_RETCODE_DONE,
            ticket=result.order,
            error=result.comment,
        )
    
    def modify_order(self, ticket, sl, tp) -> bool:
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": sl,
            "tp": tp,
        }
        result = mt5.order_send(request)
        return result.retcode == mt5.TRADE_RETCODE_DONE
```

---

## 10. File Count Comparison

| | V4 | V5 (target) |
|---|---|---|
| Top-level dirs | 29 | 10 |
| Python files | 3172 | ~150 (production only) |
| Config locations | ~15 hardcoded | 1 config.yaml |
| Broker adapters | 1 (gateway only) | 2 (direct + gateway) |
| Entry points | 3+ (engine, trailing, tracker) | 1 (run.py) |

---

## 11. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| MetaTrader5 package Windows-only | Gateway adapter still works on Linux |
| V4 changes during migration | V5 is copy, V4 untouched |
| Config.yaml too complex | Schema validation + sensible defaults |
| Strategy code needs refactor | Only import paths change, logic stays |

---

## 12. Next Steps (Kalau Boskuh Approve)

1. **Approve design** → Riri mulai Phase 1
2. **Priority:** Phase 2 (Broker Abstraction) paling krusial — ini yang bikin Windows jalan
3. **Timeline:** ~4-5 hari kerja total
4. **Testing:** Dual-test di Linux (existing) + Windows (new)

---

*"Boskuh bilang modular, Riri bikin modular. Copy-paste-run, gitu aja."* 🔥
