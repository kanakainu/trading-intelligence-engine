# TIE V4 Modular — Architecture Design

## Problem
Current TIE V4 is monolithic:
- `tie_production.py` (655 lines) = main loop + ALL logic inline
- Hardcoded paths (`/home/ubuntu/...`), hardcoded gateway URL
- Broker adapter = HTTP gateway only (Linux → Windows MT5)
- Can't deploy on Windows VPS where MT5 runs natively
- No clean install/deploy mechanism

## Goal
Self-contained `tie_v4/` folder. Copy to any machine, `pip install .`, run.
Works on:
- **Linux VPS** (current: HTTP gateway to Windows MT5)
- **Windows VPS** (direct: MetaTrader5 Python package)
- **Any OS** (mock adapter for testing)

## Architecture — Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        tie_v4/                                   │
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐   │
│  │  DATA     │───▶│ FEATURE  │───▶│ STRATEGY │───▶│  RISK    │   │
│  │  FEED     │    │  ENGINE  │    │  LAYER   │    │  GATE    │   │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘   │
│       │                                                  │       │
│       │              ┌──────────┐                        ▼       │
│       │              │  EXEC    │◀───────────────── EXECUTE      │
│       │              │  LAYER   │                                │
│       │              └──────────┘                                │
│       │                   │                                      │
│       ▼              ┌──────────┐    ┌──────────┐               │
│  ┌──────────┐        │ POSITION │───▶│ TRAILING │               │
│  │ ADAPTERS  │        │ MONITOR  │    │ MANAGER  │               │
│  │ (broker/  │        └──────────┘    └──────────┘               │
│  │  market)  │             │                                      │
│  └──────────┘        ┌──────────┐                               │
│                      │OBSERVER  │                                │
│                      │(logging, │                                │
│                      │ dashboard│                                │
│                      └──────────┘                                │
└─────────────────────────────────────────────────────────────────┘
```

## Folder Structure

```
tie_v4/                          # Root — self-contained package
├── __init__.py                  # Version, public API
├── __main__.py                  # Entry point: python -m tie_v4
├── config.py                    # All config in ONE place (env/file/CLI)
│
├── adapters/                    # Platform abstraction layer
│   ├── __init__.py
│   ├── base.py                  # Abstract interfaces (Broker, Market, DataFeed)
│   ├── mt5_gateway.py           # Linux: HTTP gateway client (current)
│   ├── mt5_native.py            # Windows: MetaTrader5 Python package
│   ├── mt5_mock.py              # Testing: simulated broker
│   └── registry.py              # Auto-detect adapter based on platform
│
├── core/                        # Pure logic — zero external deps
│   ├── __init__.py
│   ├── features/                # Feature computation (tick/candle → features)
│   │   ├── __init__.py
│   │   ├── engine.py            # FeatureEngine
│   │   └── models.py            # FeatureSnapshot
│   │
│   ├── regime/                  # Market regime detection
│   │   ├── __init__.py
│   │   ├── engine.py            # RegimeEngine
│   │   └── models.py            # Regime, TrendDirection
│   │
│   ├── opportunity/             # Opportunity window filtering
│   │   ├── __init__.py
│   │   ├── engine.py            # OpportunityEngine
│   │   └── models.py            # OpportunitySnapshot, BlockReason
│   │
│   ├── context/                 # Scan context (price, SR, session)
│   │   ├── __init__.py
│   │   ├── engine.py            # ContextEngine
│   │   └── scan_context.py      # ScanContext
│   │
│   ├── rules/                   # Risk rules (session, spread, SL/TP, lot)
│   │   ├── __init__.py
│   │   ├── registry.py          # build_risk_registry()
│   │   ├── sl_tp_validation.py
│   │   ├── spread_rule.py
│   │   └── plugins/
│   │       └── dynamic_lot.py
│   │
│   └── strategy/                # Strategy interfaces + exit logic
│       ├── __init__.py
│       ├── base.py              # BaseStrategy ABC
│       ├── result.py            # StrategyResult, TradePlan
│       ├── exit_orchestrator.py # Adaptive RR, trailing config
│       └── manager.py           # StrategyManager (loads/runs strategies)
│
├── strategies/                  # Strategy implementations
│   ├── __init__.py
│   ├── bystra/                  # Bystra — 14 detectors, trend filter
│   │   ├── __init__.py
│   │   ├── strategy.py
│   │   ├── config.py
│   │   └── metadata.py
│   │
│   ├── aggressive/              # Aggressive — C7 pipeline, regime
│   │   ├── __init__.py
│   │   ├── strategy.py
│   │   ├── config.py
│   │   ├── metadata.py
│   │   ├── momentum_engine.py
│   │   ├── velocity_engine.py
│   │   ├── microstructure_engine.py
│   │   ├── liquidity_engine.py
│   │   ├── vwap_context_engine.py
│   │   ├── opportunity_window.py
│   │   ├── market_snapshot.py
│   │   ├── entry_score_engine.py
│   │   └── regime/
│   │       ├── __init__.py
│   │       └── regime_engine.py
│   │
│   └── semi_hft/                # SemiHFT — C8, microstructure
│       ├── __init__.py
│       ├── strategy.py
│       ├── config.py
│       ├── metadata.py
│       ├── entry_score.py
│       ├── fast_risk.py
│       ├── daily_governor.py
│       ├── tick_velocity_engine.py
│       ├── volatility_engine.py
│       ├── recovery_engine.py
│       ├── opportunity_window.py
│       ├── position_heat.py
│       ├── micro_momentum_engine.py
│       ├── market_pulse_engine.py
│       ├── market_snapshot.py
│       ├── liquidity_map.py
│       └── exit_intelligence.py
│
├── detectors/                   # Pattern detectors (Bystra C1-C6)
│   ├── __init__.py
│   ├── common.py                # find_swing_pivots, sl_buffer, etc.
│   ├── snrc1_detector.py
│   ├── snrc2_detector.py
│   ├── snrc3_detector.py
│   ├── qmc_detector.py
│   ├── qmm_detector.py
│   ├── qmr_detector.py
│   ├── qm2p_detector.py
│   ├── mother_candle_detector.py
│   ├── blindspot_detector.py
│   ├── blindspot2_detector.py
│   ├── hybrid1_detector.py
│   ├── hybrid2_detector.py
│   ├── clab_detector.py
│   ├── manipulation_detector.py
│   └── regime_hmm.py
│
├── runtime/                     # Orchestration — wires everything
│   ├── __init__.py
│   ├── engine.py                # TIEEngine — main class (replaces tie_production.py)
│   ├── multi_strategy.py        # MultiStrategyRuntime (fusion)
│   ├── tradeplan_adapter.py     # plan_to_decision()
│   ├── contract_executor.py     # BE, trailing, partial TP
│   ├── position_monitor.py      # Watches positions, triggers executor
│   ├── trailing_manager.py      # TrailingManager callback
│   ├── trade_tracker.py         # TradeOutcomeTracker (win/loss)
│   └── health_monitor.py        # HealthMonitor
│
├── governance/                  # Risk & budget management
│   ├── __init__.py
│   ├── daily_governor.py        # DailyProfitGovernorV2
│   ├── trade_budget.py          # TradeBudgetManager
│   ├── opportunity_lifecycle.py # OpportunityLifecycle
│   ├── adaptive_threshold.py    # AdaptiveThresholdManager
│   └── portfolio.py             # PortfolioCoordinator
│
├── observatory/                 # Monitoring & analytics
│   ├── __init__.py
│   ├── gate_observatory.py      # GateObservatory (SQLite)
│   ├── execution_tracker.py     # ExecutionTracker
│   └── postmortem.py            # PostMortemAnalyzer
│
├── dashboard/                   # Optional web dashboard
│   ├── __init__.py
│   ├── server.py                # FastAPI app (port 3002)
│   ├── routers/
│   │   └── dashboard.py
│   ├── static/
│   │   ├── index.html
│   │   ├── app.js
│   │   └── style.css
│   └── README.md
│
├── scripts/                     # Utility scripts
│   ├── install.sh               # pip install + deps
│   ├── install.bat              # Windows install
│   ├── kill_zombies.sh
│   ├── test_gateway.py
│   └── trade_tracker.py
│
├── config/                      # Default configs (user overwrites)
│   ├── engine.yaml              # Main engine config
│   ├── strategies.yaml          # Strategy toggles + params
│   ├── risk.yaml                # Risk gate params
│   └── trailing.yaml            # Trailing profiles
│
├── data/                        # Runtime data (gitignored)
│   ├── day_start.json
│   ├── wins.json
│   └── tracker_state.json
│
├── logs/                        # Runtime logs (gitignored)
│   └── tie_v4.log
│
├── pyproject.toml               # pip install metadata
├── setup.py                     # Backward compat
├── requirements.txt             # Core deps
├── requirements-win.txt         # Windows-specific (MetaTrader5)
├── requirements-dev.txt         # Testing deps
├── Makefile                     # make install / make run / make test
├── Dockerfile                   # Optional container
├── README.md                    # Quick start guide
└── CHANGELOG.md
```

## Config System

All config in ONE YAML file, overridable by env vars:

```yaml
# config/engine.yaml
engine:
  symbols: ["XAUUSD"]
  scan_interval: 10          # seconds between scans
  dedup_window: 120          # seconds
  daily_target: 30.0         # USD
  daily_loss_limit: 80.0     # USD
  hibernate_interval: 1200   # seconds

adapters:
  broker: auto               # auto | mt5_gateway | mt5_native | mock
  market: auto               # auto | mt5_gateway | mt5_native | mock
  
  mt5_gateway:
    url: ${MT5_GATEWAY_URL}  # env var
    token: ${MT5_GATEWAY_TOKEN}
    timeout: 15

  mt5_native:
    login: ${MT5_LOGIN}
    password: ${MT5_PASSWORD}
    server: ${MT5_SERVER}

strategies:
  bystra:
    enabled: true
    weight: 1.0
  aggressive:
    enabled: true
    weight: 1.0
  semi_hft:
    enabled: true
    weight: 1.0

risk:
  max_lot: 0.5
  min_confidence: 0.55
  allowed_sessions: ["LONDON", "NEW_YORK", "OVERLAP", "ASIA"]
  
  lot_sizing:
    mode: flat               # flat | dynamic
    flat_lot: 0.01           # used when mode=flat (recommended for <$2000 equity)
    equity_tiers:            # used when mode=dynamic
      - [100, 400, 0.03]
      - [400, 800, 0.05]
      - [800, 2000, 0.10]
      - [2000, 5000, 0.20]

trailing:
  profiles:
    B:   # Bystra
      be_trigger_atr: 0.5
      trail_trigger_atr: 1.0
      trail_offset_atr: 0.3
      partial_tp_pct: 0.5
    A:   # Aggressive
      be_trigger_atr: 0.3
      trail_trigger_atr: 0.6
      trail_offset_atr: 0.25
      partial_tp_pct: 0.4
    S:   # SemiHFT
      be_trigger_atr: 0.15
      trail_trigger_atr: 0.3
      trail_offset_atr: 0.15
      partial_tp_pct: 0.3
```

Env var override: `TIE_SYMBOLS=BTCUSD,XAUUSD python -m tie_v4`

## Adapter Pattern

```python
# adapters/base.py
class BrokerAdapter(ABC):
    @abstractmethod
    def submit_order(self, req: OrderRequest) -> OrderResponse: ...
    @abstractmethod
    def modify_order(self, ticket: str, sl: float, tp: float) -> OrderResponse: ...
    @abstractmethod
    def close_position(self, ticket: str) -> OrderResponse: ...
    @abstractmethod
    def get_positions(self) -> List[Position]: ...
    @abstractmethod
    def get_account(self) -> AccountInfo: ...

class MarketDataAdapter(ABC):
    @abstractmethod
    def get_candles(self, symbol: str, timeframe: str, count: int) -> List[Candle]: ...
    @abstractmethod
    def get_price(self, symbol: str) -> PriceQuote: ...
    @abstractmethod
    def get_spread(self, symbol: str) -> float: ...

# adapters/mt5_native.py — Windows direct
import MetaTrader5 as mt5

class MT5NativeBroker(BrokerAdapter):
    def initialize(self):
        mt5.initialize()
        mt5.login(self.login, self.password, self.server)
    
    def submit_order(self, req):
        result = mt5.order_send({
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": req.symbol,
            "volume": req.volume,
            "type": mt5.ORDER_TYPE_BUY if req.direction == "buy" else mt5.ORDER_TYPE_SELL,
            "sl": req.sl,
            "tp": req.tp,
            "comment": req.comment,
        })
        return OrderResponse(...)

# adapters/mt5_gateway.py — Linux via HTTP
class MT5GatewayBroker(BrokerAdapter):
    def __init__(self, url, token):
        self.client = MT5GatewayClient(url, token)
    
    def submit_order(self, req):
        resp = self.client.trade(req.symbol, req.direction, req.volume, ...)
        return OrderResponse(...)
```

## Entry Point

```python
# __main__.py
import argparse
from tie_v4.config import load_config
from.tie_v4.adapters.registry import create_broker, create_market
from tie_v4.runtime.engine import TIEEngine

def main():
    parser = argparse.ArgumentParser(description="TIE V4 Trading Engine")
    parser.add_argument("--config", default="config/engine.yaml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    cfg = load_config(args.config)
    broker = create_broker(cfg.adapters)
    market = create_market(cfg.adapters)
    
    engine = TIEEngine(
        broker=broker,
        market=market,
        config=cfg,
        dry_run=args.dry_run,
    )
    engine.run()  # Main loop

if __name__ == "__main__":
    main()
```

## Pipeline Flow (engine.py — replaces tie_production.py)

```
while True:
    1. heartbeat + halt check
    2. hibernate check (daily target)
    3. market open check (weekend)
    4. for each symbol:
       a. FETCH DATA     → market.get_candles() + market.get_price()
       b. FEATURES       → feature_engine.compute(candles)
       c. REGIME         → regime_engine.detect(features)
       d. CONTEXT        → context_engine.build(price, candles, session)
       e. OPPORTUNITY    → opportunity_engine.evaluate(features, regime)
       f. STRATEGIES     → strategy_manager.run_all(context, features)
       g. FUSION         → multi_strategy.fuse(results)
       h. RISK GATE      → risk_registry.evaluate(plan, ctx)
       i. EXECUTE        → broker.submit_order(decision)
       j. PUSH TO OBS    → observatory.record(decision, result)
    5. POSITION MONITOR  → check all positions, apply trailing/BE/close
    6. sleep(scan_interval)
```

## Deployment Scenarios

### Scenario A: Current Linux VPS (HTTP Gateway)
```bash
# Install
cd tie_v4/
pip install -e .

# Configure
export MT5_GATEWAY_URL="https://your-cloudflare-tunnel.trycloudflare.com"
export MT5_GATEWAY_TOKEN="your-token"

# Run
python -m tie_v4 --config config/engine.yaml
# Or with systemd:
sudo systemctl start tie-v4.service
```

### Scenario B: Windows VPS (MT5 Native)
```bash
# Install
cd tie_v4/
pip install -e ".[windows]"
# This installs MetaTrader5 package

# Configure
set MT5_LOGIN=12345678
set MT5_PASSWORD=your-password
set MT5_SERVER=Exness-MT5Trial14

# Run
python -m tie_v4 --config config/engine.yaml
```

### Scenario C: Testing (Mock)
```bash
python -m tie_v4 --config config/engine.yaml --dry-run
# Uses mt5_mock.py — no real trades, simulated data
```

## Migration Plan

### Phase 1: Extract (Week 1)
1. Create `tie_v4/` folder structure
2. Copy existing files into new structure (preserve logic)
3. Remove hardcoded paths → use `config.py` + env vars
4. Extract `tie_production.py` monolith → `runtime/engine.py`
5. Create adapter base classes + move `mt5_broker.py` → `adapters/mt5_gateway.py`

### Phase 2: Abstract (Week 2)
1. Create `adapters/mt5_native.py` (Windows MetaTrader5 package)
2. Create `adapters/mt5_mock.py` (testing)
3. Create `adapters/registry.py` (auto-detect platform)
4. Wire config system (YAML + env vars)
5. Create `pyproject.toml` + `requirements.txt`

### Phase 3: Validate (Week 3)
1. Test on current Linux VPS (regression — same behavior)
2. Test on Windows VPS (new MT5 native adapter)
3. Test mock adapter (unit tests)
4. Dashboard standalone extraction
5. Documentation

### Phase 4: Ship
1. `pip install tie_v4` works
2. `python -m tie_v4` starts engine
3. systemd service template
4. Windows Task Scheduler template
5. README with quick-start

## Key Design Decisions

1. **Adapter pattern** — Broker/Market adapters are swappable. Core logic never touches MT5 API directly.
2. **Config-first** — Zero hardcoded values. All params in YAML, overridable by env vars.
3. **Flat lot default** — For equity < $2000, always use `flat_lot: 0.01`. Dynamic lot is opt-in.
4. **Dashboard optional** — Dashboard is separate `tie_v4.dashboard` subpackage. Engine runs headless.
5. **No AI/LLM dependency** — Core engine is rule-based. LLM reasoner is optional plugin.
6. **Single entry point** — `python -m tie_v4` does everything. No multiple scripts to manage.
7. **Data persistence** — `data/` folder for day_start, wins, tracker state. Survives restart.
8. **Gateway still supported** — `adapters/mt5_gateway.py` wraps existing HTTP gateway for Linux→Windows setup.
9. **Dual trailing consolidation** — Merge TrailingManager + PositionMonitor into single executor (current bug #38).
10. **Halt flag** — `touch data/halt` stops trading. `rm data/halt` resumes. Works on all OS.

## File Count Estimate
- Adapters: ~5 files
- Core (features, regime, opportunity, context, rules, strategy): ~25 files
- Strategies: ~35 files (mostly existing, restructured)
- Detectors: ~16 files (existing, no change)
- Runtime: ~10 files
- Governance: ~5 files
- Observatory: ~3 files
- Dashboard: ~5 files
- Config/scripts: ~8 files
- **Total: ~112 files** (down from 200+ — consolidation removes dead code)

## Dependencies

### Core (all platforms)
```
pyyaml>=6.0
requests>=2.28
```

### Windows
```
MetaTrader5>=5.0.45
```

### Dashboard (optional)
```
fastapi>=0.100
uvicorn>=0.23
```

### Dev
```
pytest>=7.0
pytest-cov
```

## Skipped (ponytail)
- Backtest module — not needed for production, keep separate
- Vibe-Trading integration — dead code, remove
- Knowledge graph / reasoning engine — unused, remove
- SDK / compiler / pack system — unused, remove
- Skills / learning engine — unused, remove
- HCK bridge — specific to current setup, make optional
