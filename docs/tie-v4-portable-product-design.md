# TIE V4 Portable — Product Design Document
**Version:** 3.0.0  
**Date:** 2026-08-06  
**Author:** Riri (Trading Intelligence Engine)  
**Status:** Draft — Pending Boskuh Review  

---

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Target Users & Deployment Scenarios](#2-target-users--deployment-scenarios)
3. [Current Codebase Audit](#3-current-codebase-audit)
4. [Architecture](#4-architecture)
5. [Data Models](#5-data-models)
6. [Adapter Pattern (Detailed)](#6-adapter-pattern-detailed)
7. [Config System (Detailed)](#7-config-system-detailed)
8. [Error Handling & Logging](#8-error-handling--logging)
9. [Key Design Decisions](#9-key-design-decisions)
10. [Bug Fixes Baked Into Architecture](#10-bug-fixes-baked-into-architecture)
11. [Phase & Sprint Plan](#11-phase--sprint-plan)
12. [Migration Map (Old → New)](#12-migration-map-old--new)
13. [API Specifications](#13-api-specifications)
14. [Database Schemas](#14-database-schemas)
15. [Risk Matrix](#15-risk-matrix)
16. [Dependencies](#16-dependencies)
17. [Success Metrics](#17-success-metrics)
18. [Out of Scope (ponytail)](#18-out-of-scope-ponytail)
19. [Glossary](#19-glossary)
20. [Sprint Dependency Graph](#20-sprint-dependency-graph)
21. [Effort Estimates](#21-effort-estimates)
22. [Config Validation Schema](#22-config-validation-schema)
23. [Testing Strategy](#23-testing-strategy)
24. [Rollback Procedures](#24-rollback-procedures)
25. [Performance Baseline](#25-performance-baseline)

---

## 1. Executive Summary

TIE V4 Portable = self-contained trading engine. Copy folder → pip install → run. No hardcoded paths, no OS-specific assumptions, no external process dependencies.

**Problem:** Current TIE V4 is monolithic (`tie_production.py` 655 lines, hardcoded paths, Linux-only HTTP gateway, **3172 .py files** scattered across 60+ directories). Can't deploy on Windows VPS where MT5 runs natively. No clean install/deploy. Every bug fix creates 2 new bugs from hidden coupling. Dead code from over-engineered modules (knowledge graph, reasoning engine, compiler, SDK, Vibe-Trading) inflates maintenance cost.

**Solution:** Single `tie_v4/` package. Adapter pattern for broker/market. Config-first (YAML + env vars). Flat lot default. Dashboard optional. One entry point: `python -m tie_v4`. **~112 files total** (down from 3172).

**Success Criteria:**
- `pip install .` works on Linux, Windows, macOS
- `python -m tie_v4` starts engine (no manual process management)
- Zero hardcoded paths/URLs in source code
- Same trading behavior as current production (regression pass)
- Dashboard optional (engine runs headless)
- Single systemd service / Windows Task Scheduler entry
- Scan cycle < 5s, memory < 200MB RSS after 24h

---

## 2. Target Users & Deployment Scenarios

| Scenario | OS | Broker | Use Case |
|----------|----|--------|----------|
| **A. Linux VPS** | Ubuntu 22+ | HTTP Gateway (Cloudflare tunnel) | Current production. Engine on Linux, MT5 on Windows. |
| **B. Windows VPS** | Windows 10+ | MetaTrader5 Python package (native) | Direct MT5 access. No gateway needed. |
| **C. Local Dev** | Any | Mock adapter | Testing strategies, backtesting, dry-run. |
| **D. Docker** | Any | HTTP Gateway or Native | Containerized deploy. |

---

## 3. Current Codebase Audit

### 3.1 File Count by Area

| Area | .py Files | Status | Action |
|------|-----------|--------|--------|
| `runtime/` | 47 | Mixed — `tie_production.py` (655L) core, rest mostly dead | Extract ~15, archive rest |
| `core/` | ~140 | Heavy dead code (knowledge graph, reasoning, explanation, compiler, query, facts) | Extract ~30, delete rest |
| `strategies/` | ~60 | All 3 strategies active | Migrate all, clean dead code |
| `detectors/` | ~20 | All 14 detectors active | Migrate all |
| `adapters/broker/` | 5 | `mt5_broker.py` (179L) active | Wrap into new adapter |
| `adapters/market/` | 3 | Partially used | Merge into broker adapter |
| `config/` | 5 | Active | Merge into single YAML |
| `plugins/` | 10 | Mixed | Extract `dynamic_lot.py` only |
| `scripts/` | 10 | Operational | Migrate to `scripts/` |
| `knowledge/` | 50+ | DEAD — knowledge graph system | DELETE |
| `sdk/` | 20+ | DEAD — unused SDK | DELETE |
| `Vibe-Trading/` | 100+ | DEAD — frontend project | DELETE |
| `reasoning/` | 15+ | DEAD — reasoning engine | DELETE |
| `backtest/` | 20 | Separate project, not production | EXCLUDE |
| `tests/` | 30 | Mixed quality | Rewrite from scratch |
| **TOTAL** | **3172** | | **→ ~112** |

### 3.2 What Gets Extracted (Production-Critical)

| Current File | Lines | New Location | Notes |
|-------------|-------|-------------|-------|
| `runtime/tie_production.py` | 655 | `runtime/engine.py` | Refactored into TIEEngine class |
| `runtime/multi_strategy_runtime.py` | 109 | `runtime/multi_strategy.py` | Fusion logic |
| `runtime/contract_executor.py` | 144 | `runtime/contract_executor.py` | BE, trailing, partial TP |
| `runtime/position_monitor.py` | 75 | `runtime/position_monitor.py` | Position watching |
| `runtime/trailing_manager.py` | ? | `runtime/trailing_manager.py` | Consolidated (eliminate manual_trailing_v2) |
| `runtime/trade_outcome_tracker.py` | ? | `runtime/trade_tracker.py` | Win/loss tracking |
| `runtime/tradeplan_adapter.py` | ? | `runtime/tradeplan_adapter.py` | plan_to_decision() |
| `runtime/gate_observatory.py` | ? | `observatory/gate_observatory.py` | SQLite recording |
| `runtime/health_monitor.py` | ? | `runtime/health_monitor.py` | Heartbeat, uptime |
| `core/features/feature_engine.py` | 354 | `core/features/engine.py` | Feature computation |
| `core/features/feature_models.py` | ? | `core/features/models.py` | FeatureSnapshot dataclass |
| `core/regime/regime_engine.py` | ? | `core/regime/engine.py` | Regime detection |
| `core/regime/regime_models.py` | ? | `core/regime/models.py` | Regime enum |
| `core/opportunity/opportunity_engine.py` | ? | `core/opportunity/engine.py` | Opportunity evaluation |
| `core/context/scan_context.py` | ? | `core/context/scan_context.py` | ScanContext model |
| `core/context/context_engine.py` | ? | `core/context/engine.py` | Context building |
| `core/rules/risk/risk_registry.py` | 40 | `core/rules/registry.py` | Risk gate assembly |
| `core/rules/risk/sl_tp_validation.py` | ? | `core/rules/sl_tp_validation.py` | TP validation |
| `core/rules/risk/spread_rule.py` | ? | `core/rules/spread_rule.py` | Spread filter |
| `core/rules/plugins/dynamic_lot.py` | ? | `core/rules/plugins/dynamic_lot.py` | Lot tiers |
| `core/strategy/base_strategy.py` | ? | `core/strategy/base.py` | BaseStrategy ABC |
| `core/strategy/strategy_result.py` | ? | `core/strategy/result.py` | StrategyResult, TradePlan |
| `core/strategy/exit_orchestrator.py` | ? | `core/strategy/exit_orchestrator.py` | TP optimization |
| `strategies/bystra/*` | 132+ | `strategies/bystra/` | All 14 detectors |
| `strategies/aggressive/*` | 172+ | `strategies/aggressive/` | C7 pipeline |
| `strategies/semi_hft/*` | 179+ | `strategies/semi_hft/` | C8 pipeline |
| `detectors/*` | 1513 total | `detectors/` | 14 Bystra detectors |
| `adapters/broker/mt5_broker.py` | 179 | `adapters/mt5_gateway.py` | Rewritten |

### 3.3 What Gets Deleted (Dead Code)

| Area | Files | Why Dead |
|------|-------|----------|
| `core/knowledge/`, `core/graph/`, `core/query/` | ~30 | Knowledge graph never used in production |
| `core/reasoning/`, `core/explanation/` | ~20 | Reasoning engine never wired to production loop |
| `core/compiler/`, `core/facts/`, `core/patterns/` | ~25 | Compiler/pack system unused |
| `core/compatibility/`, `core/compat/` | ~10 | Migration guards for schemas that don't exist |
| `core/validator/`, `core/schema/` | ~10 | Validators for unused subsystems |
| `core/learning/`, `core/lifecycle/` | ~5 | LearningBrain stub only |
| `core/fusion/` | ~3 | Replaced by runtime/multi_strategy |
| `core/decision/` | ~15 | Over-engineered decision pipeline, replaced by simpler flow |
| `core/setup/` | ~15 | Setup compiler/registry unused |
| `core/signals/` | ~2 | Replaced by core/strategy/result.py |
| `core/registry/` | ~3 | Strategy registry unused |
| `core/relationships/` | ~4 | Relationship models unused |
| `sdk/` | ~20+ | SDK never used in production |
| `Vibe-Trading/` | ~100+ | Frontend project, not trading engine |
| `knowledge/` | ~50+ | Knowledge base for reasoning engine |
| `runtime/_archive/` | ~20 | Already archived |
| `runtime/hck_wire.py`, `runtime/compiler_bridge.py`, etc. | ~15 | Dead wiring |
| **TOTAL DELETED** | **~400+ files** | |

---

## 4. Architecture

### 4.1 Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         TIE V4 ENGINE                                │
│                                                                      │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐         │
│  │  DATA    │──▶│ FEATURE  │──▶│ STRATEGY │──▶│  RISK    │         │
│  │  FEED    │   │  ENGINE  │   │  LAYER   │   │  GATE    │         │
│  └──────────┘   └──────────┘   └──────────┘   └────┬─────┘         │
│       │                                             │                │
│       │              ┌──────────┐                   ▼                │
│       │              │  EXEC    │◀──────────── PASS / FAIL          │
│       │              │  LAYER   │                                     │
│       │              └────┬─────┘                                     │
│       │                   │                                           │
│       ▼              ┌────┴──────┐   ┌──────────┐                   │
│  ┌──────────┐        │ POSITION  │──▶│ TRAILING │                   │
│  │ ADAPTERS │        │ MONITOR   │   │ MANAGER  │                   │
│  │ (broker/ │        └────┬──────┘   └──────────┘                   │
│  │  market) │             │                                          │
│  └──────────┘        ┌────┴──────┐                                  │
│                      │ OBSERVER  │                                   │
│                      │ (logging, │                                   │
│                      │ dashboard)│                                   │
│                      └──────────┘                                    │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Main Loop (engine.py — replaces tie_production.py)

```python
class TIEEngine:
    """Single-process engine. Replaces tie_production.py (655 lines)."""

    def __init__(self, config: EngineConfig, broker: BrokerAdapter, market: MarketDataAdapter):
        self.config = config
        self.broker = broker
        self.market = market
        self.feature_engine = FeatureEngine()
        self.regime_engine = RegimeEngine()
        self.opportunity_engine = OpportunityEngine()
        self.context_engine = ContextEngine()
        self.strategy_manager = StrategyManager(config.strategies)
        self.risk_registry = build_risk_registry(config.risk)
        self.trailing_manager = TrailingManager(broker, config.trailing)
        self.position_monitor = PositionMonitor(broker, self.trailing_manager)
        self.governor = DailyProfitGovernorV2(config.engine.daily_target)
        self.observatory = GateObservatory(config.observatory.db_path)
        self.health = HealthMonitor(config.data_dir)

    def run(self):
        """Main loop — replaces while True block in tie_production.py."""
        while True:
            self.health.write_heartbeat()
            
            # Halt check
            if self._halt_flag_exists():
                logger.info("HALT flag detected. Sleeping 60s.")
                time.sleep(60)
                continue
            
            # Daily target hibernate
            equity = self.broker.get_account().equity
            if self.governor.target_hit(equity):
                self._hibernate()
                continue
            
            # Weekend guard
            if self._is_weekend():
                logger.info("Weekend. Sleeping 300s.")
                time.sleep(300)
                continue
            
            # Scan each symbol
            for symbol in self.config.engine.symbols:
                try:
                    self._scan_symbol(symbol, equity)
                except Exception as e:
                    logger.error(f"Scan error {symbol}: {e}", exc_info=True)
            
            # Position monitor (trailing, BE, close)
            try:
                self.position_monitor.monitor_all()
            except Exception as e:
                logger.error(f"Position monitor error: {e}", exc_info=True)
            
            # Sleep
            time.sleep(self.config.engine.scan_interval)

    def _scan_symbol(self, symbol: str, equity: float):
        """Single symbol scan — the 10-step pipeline."""
        # 1. FETCH
        candles = {}
        for tf in ["M1", "M5", "M15", "H1", "H4"]:
            candles[tf] = self.market.get_candles(symbol, tf, 250)
        price = self.market.get_price(symbol)
        
        # 2. FEATURES
        features = self.feature_engine.compute(candles)
        
        # 3. REGIME
        regime = self.regime_engine.detect(features)
        
        # 4. CONTEXT
        context = self.context_engine.build(price, candles, self._current_session())
        
        # 5. OPPORTUNITY
        opp = self.opportunity_engine.evaluate(features, regime, symbol)
        if not opp.open:
            return  # Market conditions unfavorable
        
        # 6. STRATEGIES
        results = self.strategy_manager.run_all(context, features)
        if not results:
            return  # No signals
        
        # 7. FUSION
        fused = MultiStrategyRuntime.fuse(results)
        if not fused:
            return  # No viable fusion
        
        # 8. TRADE PLAN
        plan = self._build_trade_plan(fused, context, features)
        
        # 9. RISK GATE
        risk_ctx = self._build_risk_context(plan, equity)
        decision = self.risk_registry.evaluate(plan, risk_ctx)
        
        # 10. EXECUTE or OBSERVE
        if decision.passed:
            order = plan_to_decision(plan)
            order.metadata["volume"] = self._lot(equity)  # Fix #29
            self.broker.submit_order(order)
            logger.info(f"EXECUTED: {order}")
        
        self.observatory.record(decision, plan)
```

### 4.3 Component Responsibilities

| Component | Input | Output | External Deps |
|-----------|-------|--------|---------------|
| **DataFeed** (adapter) | symbol, tf, count | Candle[], PriceQuote | MT5 Gateway / Native / Mock |
| **FeatureEngine** | Candle[] | FeatureSnapshot | None (pure math) |
| **RegimeEngine** | FeatureSnapshot | Regime (TRENDING/RANGING/CHOPPY) | None |
| **ContextEngine** | price, candles, session | ScanContext | None |
| **OpportunityEngine** | features, regime | OpportunitySnapshot (open/closed + reason) | None |
| **StrategyManager** | context, features | StrategyResult[] (signal + trade plan) | Detectors (Bystra) |
| **MultiStrategy** | StrategyResult[] | Fused TradePlan (score, direction, SL/TP) | None |
| **RiskRegistry** | plan, risk_ctx | PASS/FAIL + reason | None |
| **ContractExecutor** | position, config | BE lock, trail, partial TP | Broker adapter |
| **PositionMonitor** | positions[] | ExecutionResult[] | Broker adapter |
| **Observer** | decision, result | Logs, DB, dashboard data | SQLite (optional) |

### 4.4 Threading Model

**Single-threaded main loop.** No concurrency, no asyncio, no thread pool.

Rationale:
- Trading engine scans every 10s — no latency requirement for threading
- Single-thread eliminates race conditions (fix #38: triple trailing systems)
- Position monitoring runs inline after scan (same tick)
- Dashboard runs as separate process (optional), reads shared state from files/DB

```
Main Thread (engine.py):
  while True:
    scan symbols (sequential)
    monitor positions (sequential)
    sleep 10s

Separate Process (optional):
  dashboard/server.py (FastAPI, reads gate_observatory.db + gateway)
```

**Exception:** Trade outcome tracker runs as a separate thread within the engine process (polls positions every 15s). Uses thread-safe Queue for communication.

### 4.5 State Management

| State | Storage | Persistence | Survives Reboot |
|-------|---------|-------------|-----------------|
| Day-start balance | `data/day_start.json` + `/tmp/tie_day_start.json` | Dual-write | Yes (data/ persists) |
| Heartbeat timestamp | `data/heartbeat.txt` | Single write | No (recovers on next write) |
| Halt flag | `data/halt` | File existence | Yes |
| Trade wins/losses | `data/wins.json` | Single write | No (tracker rebuilds) |
| Gate decisions | `data/gate_observatory.db` (SQLite) | Append-only | Yes |
| Engine config | `config/engine.yaml` | Static file | Yes |
| Runtime state | In-memory only | Lost on crash | Engine re-scans on restart |

**Day-start dual-write pattern (fix #41):**
```python
def _save_day_start(self, balance: float):
    payload = json.dumps({"balance": balance, "date": date.today().isoformat()})
    # Persist first (survives reboot)
    with open(self.config.data_dir / "day_start.json", "w") as f:
        f.write(payload)
    # Then fast-access copy
    with open("/tmp/tie_day_start.json", "w") as f:
        f.write(payload)

def _load_day_start(self) -> float:
    persist = self.config.data_dir / "day_start.json"
    tmp = Path("/tmp/tie_day_start.json")
    # Always prefer persisted (fix #41)
    path = persist if persist.exists() else tmp
    data = json.loads(path.read_text())
    return data["balance"]
```

---

## 5. Data Models

### 5.1 Core Models (`core/models.py`)

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Any

# --- Market Data ---

@dataclass
class Candle:
    timestamp: float       # Unix epoch
    open: float
    high: float
    low: float
    close: float
    volume: float          # Tick volume (MT5)
    timeframe: str         # "M1", "M5", "M15", "H1", "H4"

@dataclass
class PriceQuote:
    symbol: str
    bid: float
    ask: float
    spread: float          # Points
    timestamp: float

@dataclass
class AccountInfo:
    balance: float
    equity: float
    margin: float
    free_margin: float
    profit: float          # Floating P&L

@dataclass
class Position:
    ticket: str
    symbol: str
    direction: str         # "buy" | "sell"
    volume: float          # Lot size
    entry_price: float
    stop_loss: float
    take_profit: float
    profit: float
    comment: str           # Strategy decode: "TIE_B_BUY"
    open_time: float

# --- Orders ---

@dataclass
class OrderRequest:
    symbol: str
    direction: str         # "buy" | "sell"
    volume: float          # Lot size (NOT 'lot' — fix #29)
    stop_loss: float
    take_profit: float
    comment: str           # "TIE_B_BUY" etc.
    magic: int = 20260806

@dataclass
class OrderResponse:
    success: bool
    ticket: Optional[str] = None
    error: Optional[str] = None

# --- Features ---

@dataclass
class FeatureSnapshot:
    atr: Dict[str, float]          # {"M5": 5.2, "H1": 12.8} — NOT float (pitfall)
    volume_ratio: Dict[str, float] # {"M5": 1.3, "H1": 0.9}
    session: str                    # "ASIA" | "LONDON" | "NEW_YORK" | "OVERLAP"
    regime_hint: str                # "TRENDING" | "RANGING" | "CHOPPY"
    # NOTE: NO current_price field (bug #14 prevention)
    # Price lives in ScanContext.current_price

# --- Regime ---

class Regime(Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    CHOPPY = "choppy"
    LOW_LIQUIDITY = "low_liquidity"

@dataclass
class RegimeSnapshot:
    regime: Regime
    confidence: float      # 0.0-1.0
    reason: str

# --- Opportunity ---

@dataclass
class OpportunitySnapshot:
    open: bool             # Can we trade?
    score: float           # 0-100
    reason: str            # Why blocked if not open
    session_score: float   # Session-specific score

# --- Context ---

@dataclass
class ScanContext:
    current_price: float
    session: str
    symbol: str
    sr_levels: Dict[str, List[float]]  # {"support": [...], "resistance": [...]}
    metadata: Dict[str, Any] = field(default_factory=dict)

# --- Strategy ---

@dataclass
class StrategyResult:
    signal: Optional['Signal'] = None
    strategy_code: str = ""        # "B" | "A" | "S"
    strategy_name: str = ""        # "Bystra" | "Aggressive" | "SemiHFT"
    score: float = 0.0             # 0-100
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Signal:
    direction: str                 # "buy" | "sell"
    entry_zone: Dict[str, float]   # {"low": price-0.5, "high": price+0.5}
    stop_loss: float
    take_profit: float
    confidence: float              # 0.0-1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TradePlan:
    symbol: str
    action: str                    # "buy" | "sell"
    entry_zone: Dict[str, float]
    stop_loss: float
    take_profit: float
    lot: float
    score: float
    strategy_code: str             # "B", "A", "S", "BA", "BAS"
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TradeDecision:
    symbol: str
    direction: str                 # "buy" | "sell"
    volume: float                  # Lot size
    stop_loss: float
    take_profit: float
    comment: str                   # "TIE_B_BUY"
    metadata: Dict[str, Any] = field(default_factory=dict)

# --- Risk ---

@dataclass
class RiskContext:
    entry: float
    sl: float
    tp: float
    lot: float                     # From decision.metadata["volume"], NEVER hardcoded
    equity: float
    session: str
    symbol: str
    strategy_code: str

@dataclass
class RiskDecision:
    passed: bool
    reason: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

# --- Execution ---

@dataclass
class ExecutionResult:
    action: str                    # "be_lock" | "trail" | "partial_tp" | "close"
    position_ticket: str
    new_sl: Optional[float] = None
    new_tp: Optional[float] = None
    reason: str = ""
```

### 5.2 Setup Naming Convention

| Contributing Strategies | Setup Name | Order Comment |
|------------------------|------------|---------------|
| Bystra only | `B_BUY` / `B_SELL` | `TIE_B_BUY` |
| Aggressive only | `A_BUY` / `A_SELL` | `TIE_A_BUY` |
| SemiHFT only | `S_BUY` / `S_SELL` | `TIE_S_BUY` |
| Bystra + Aggressive | `BA_BUY` / `BA_SELL` | `TIE_BA_BUY` |
| All three | `BAS_BUY` / `BAS_SELL` | `TIE_BAS_BUY` |

---

## 6. Adapter Pattern (Detailed)

### 6.1 Abstract Interfaces

```python
# adapters/base.py
from abc import ABC, abstractmethod
from typing import List, Optional

class BrokerAdapter(ABC):
    """All broker interaction goes through this interface. Core logic NEVER touches MT5 API directly."""
    
    @abstractmethod
    def submit_order(self, req: OrderRequest) -> OrderResponse:
        """Submit market order. Returns ticket on success."""
        ...
    
    @abstractmethod
    def modify_order(self, ticket: str, stop_loss: float, take_profit: float) -> OrderResponse:
        """Modify SL/TP. ALWAYS sends both sl AND tp (fix #35 — gateway full-replace)."""
        ...
    
    @abstractmethod
    def close_position(self, ticket: str) -> OrderResponse:
        """Close position by ticket."""
        ...
    
    @abstractmethod
    def get_positions(self) -> List[Position]:
        """Get all open positions."""
        ...
    
    @abstractmethod
    def get_account(self) -> AccountInfo:
        """Get account info (balance, equity, etc.)."""
        ...

class MarketDataAdapter(ABC):
    """All market data goes through this interface."""
    
    @abstractmethod
    def get_candles(self, symbol: str, timeframe: str, count: int) -> List[Candle]:
        """Fetch OHLCV candles."""
        ...
    
    @abstractmethod
    def get_price(self, symbol: str) -> PriceQuote:
        """Get current bid/ask/spread."""
        ...
```

### 6.2 Implementations

**MT5 Gateway (Linux → Windows HTTP bridge):**
```python
# adapters/mt5_gateway.py
class MT5GatewayBroker(BrokerAdapter):
    def __init__(self, url: str, token: str, timeout: int = 10):
        self.url = url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {token}"
        self._session.verify = False  # Cloudflare tunnel self-signed
    
    def modify_order(self, ticket: str, stop_loss: float, take_profit: float) -> OrderResponse:
        """Gateway requires BOTH sl AND tp — never partial (fix #35)."""
        payload = {
            "ticket": ticket,
            "sl": round(stop_loss, 5),
            "tp": round(take_profit, 5),
        }
        resp = self._session.post(f"{self.url}/trade/modify", json=payload, timeout=self.timeout)
        if resp.status_code == 422:
            return OrderResponse(success=False, error=resp.text)
        resp.raise_for_status()
        return OrderResponse(success=True)
```

**MT5 Native (Windows direct):**
```python
# adapters/mt5_native.py
class MT5NativeBroker(BrokerAdapter):
    def __init__(self, login: int, password: str, server: str):
        import MetaTrader5 as mt5
        self.mt5 = mt5
        if not mt5.initialize():
            raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")
        if not mt5.login(login, password=password, server=server):
            raise RuntimeError(f"MT5 login failed: {mt5.last_error()}")
    
    def modify_order(self, ticket: str, stop_loss: float, take_profit: float) -> OrderResponse:
        request = {
            "action": self.mt5.TRADE_ACTION_SLTP,
            "position": int(ticket),
            "sl": stop_loss,
            "tp": take_profit,
        }
        result = self.mt5.order_send(request)
        return OrderResponse(success=result.retcode == self.mt5.TRADE_RETCODE_DONE)
```

**Mock (Testing):**
```python
# adapters/mt5_mock.py
class MT5MockBroker(BrokerAdapter):
    def __init__(self):
        self._positions: Dict[str, Position] = {}
        self._account = AccountInfo(balance=300.0, equity=300.0, margin=0.0, free_margin=300.0, profit=0.0)
        self._next_ticket = 1000
    
    def submit_order(self, req: OrderRequest) -> OrderResponse:
        ticket = str(self._next_ticket)
        self._next_ticket += 1
        self._positions[ticket] = Position(
            ticket=ticket, symbol=req.symbol, direction=req.direction,
            volume=req.volume, entry_price=0.0,  # Mock price
            stop_loss=req.stop_loss, take_profit=req.take_profit,
            profit=0.0, comment=req.comment, open_time=time.time()
        )
        return OrderResponse(success=True, ticket=ticket)
```

### 6.3 Adapter Registry (Auto-Detect)

```python
# adapters/registry.py
def create_broker(config: dict) -> BrokerAdapter:
    mode = config.get("broker", "auto")
    
    if mode == "mock":
        return MT5MockBroker()
    
    if mode == "mt5_native":
        return MT5NativeBroker(
            login=config["mt5_native"]["login"],
            password=config["mt5_native"]["password"],
            server=config["mt5_native"]["server"],
        )
    
    if mode == "mt5_gateway":
        return MT5GatewayBroker(
            url=config["mt5_gateway"]["url"],
            token=config["mt5_gateway"]["token"],
        )
    
    if mode == "auto":
        # Auto-detect: try native first (Windows), fallback to gateway
        try:
            import MetaTrader5
            return MT5NativeBroker(...)
        except ImportError:
            return MT5GatewayBroker(...)
    
    raise ValueError(f"Unknown broker mode: {mode}")
```

---

## 7. Config System (Detailed)

### 7.1 Main Config File

```yaml
# config/engine.yaml
engine:
  symbols: ["XAUUSD"]
  scan_interval: 10          # seconds between scans
  dedup_window: 120          # seconds — same direction rejected within window
  daily_target: 30.0         # USD — hibernate when equity - day_start >= this
  daily_loss_limit: 80.0     # USD — stop trading when loss exceeds this
  hibernate_interval: 1200   # seconds to sleep when target hit (20min)
  dry_run: false             # true = scan but don't execute

adapters:
  broker: auto               # auto | mt5_gateway | mt5_native | mock
  market: auto               # same as broker (shared adapter)
  mt5_gateway:
    url: ${MT5_GATEWAY_URL}  # env var expansion
    token: ${MT5_GATEWAY_TOKEN}
    timeout: 10
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
    min_entry_score: 60      # THRESHOLD — must match entry_score.py

risk:
  max_lot: 0.5
  min_confidence: 0.55
  allowed_sessions: ["LONDON", "NEW_YORK", "OVERLAP", "ASIA"]  # "ASIA" not "ASIAN" (fix #13)
  lot_sizing:
    mode: flat               # flat | dynamic
    flat_lot: 0.01           # recommended for <$2000 equity
  rules:
    - session
    - spread
    - sl_tp_validation
    - dynamic_lot
    - daily_target
  session:
    allowed: ["LONDON", "NEW_YORK", "OVERLAP", "ASIA"]
  spread:
    max_points: 50           # XAUUSD
  daily_target:
    target_usd: 30.0         # must match engine.daily_target

trailing:
  profiles:
    B:                       # Bystra — swing, wider trails
      be_trigger_atr: 0.5
      trail_trigger_atr: 1.0
      trail_offset_atr: 0.3
      partial_tp_pct: 0.5
    A:                       # Aggressive — scalping, tighter
      be_trigger_atr: 0.3
      trail_trigger_atr: 0.6
      trail_offset_atr: 0.25
      partial_tp_pct: 0.4
    S:                       # SemiHFT — fastest trigger
      be_trigger_atr: 0.15
      trail_trigger_atr: 0.3
      trail_offset_atr: 0.15
      partial_tp_pct: 0.3

observatory:
  db_path: data/gate_observatory.db
  enabled: true

dashboard:
  enabled: false             # optional subpackage
  port: 3002
  host: 0.0.0.0

logging:
  level: INFO                # DEBUG | INFO | WARNING | ERROR
  file: logs/tie_v4.log
  max_bytes: 10485760        # 10MB
  backup_count: 5
  format: "%(asctime)s %(levelname)s %(name)s %(message)s"

data_dir: data               # Relative to package root
```

### 7.2 Config Loader

```python
# config.py
import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

class ConfigLoader:
    """YAML + env var + CLI flag. Priority: CLI > env > YAML > default."""
    
    @staticmethod
    def load(path: str, cli_overrides: dict = None) -> dict:
        raw = Path(path).read_text()
        
        # Expand env vars: ${VAR} → os.environ["VAR"]
        expanded = os.path.expandvars(raw)
        
        config = yaml.safe_load(expanded)
        
        # CLI overrides
        if cli_overrides:
            ConfigLoader._deep_merge(config, cli_overrides)
        
        return config
    
    @staticmethod
    def _deep_merge(base: dict, override: dict):
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                ConfigLoader._deep_merge(base[k], v)
            else:
                base[k] = v
```

### 7.3 Override Priority

| Priority | Source | Example |
|----------|--------|---------|
| 1 (highest) | CLI flag | `python -m tie_v4 --daily-target 50` |
| 2 | Env var | `export MT5_GATEWAY_URL=https://...` |
| 3 | YAML file | `engine.daily_target: 30.0` |
| 4 (lowest) | Hardcoded default | `scan_interval=10` |

---

## 8. Error Handling & Logging

### 8.1 Error Strategy

| Layer | Error Type | Handling |
|-------|-----------|----------|
| **Adapter** | Network timeout, 422, connection refused | Retry 3x exponential backoff → raise `AdapterError` |
| **Feature/Regime** | Empty candles, invalid data | Return safe defaults, log WARNING |
| **Strategy** | No signal, detector crash | Catch per-strategy, log ERROR, continue to next |
| **Risk Gate** | Rule exception | FAIL-safe (reject), log ERROR |
| **Execution** | Order rejected, modify rejected | Log ERROR, continue (don't crash engine) |
| **Position Monitor** | Position disappears, gateway error | Log WARNING, retry next cycle |
| **Main Loop** | Any uncaught exception | Log CRITICAL, sleep 30s, continue (never crash) |

**Principle:** Engine NEVER crashes. Every exception is caught at the appropriate layer. Worst case: engine sleeps and retries.

### 8.2 Logging Architecture

```python
# runtime/logging_config.py
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(config: dict):
    level = getattr(logging, config.get("level", "INFO"))
    fmt = config.get("format", "%(asctime)s %(levelname)s %(name)s %(message)s")
    
    # Root logger
    root = logging.getLogger("tie_v4")
    root.setLevel(level)
    
    # File handler (rotating)
    if config.get("file"):
        fh = RotatingFileHandler(
            config["file"],
            maxBytes=config.get("max_bytes", 10_485_760),
            backupCount=config.get("backup_count", 5),
        )
        fh.setFormatter(logging.Formatter(fmt))
        root.addHandler(fh)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(fmt))
    root.addHandler(ch)
```

**Log format:** `2026-08-06 14:30:15 INFO tie_v4.engine EXECUTED: TIE_B_BUY XAUUSD vol=0.01 sl=3245.0 tp=3280.0`

**Log categories:**
| Logger Name | Purpose |
|-------------|---------|
| `tie_v4.engine` | Main loop, scan cycle |
| `tie_v4.adapter.gateway` | Gateway HTTP calls |
| `tie_v4.strategy.bystra` | Bystra signals |
| `tie_v4.strategy.aggressive` | Aggressive signals |
| `tie_v4.strategy.semi_hft` | SemiHFT signals |
| `tie_v4.risk` | Risk gate decisions |
| `tie_v4.trailing` | Trailing/BE actions |
| `tie_v4.observatory` | Gate recording |

---

## 9. Key Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Adapter pattern** for broker/market | Core logic never touches MT5 API. Swap adapter = swap platform. |
| 2 | **Config-first** — zero hardcoded values | All params in YAML, overridable by env vars. No `/home/ubuntu/` in source. |
| 3 | **Flat lot default** for equity < $2000 | Prevents the $115 loss bug (fix #29). Dynamic lot is opt-in. |
| 4 | **Dashboard optional** | Engine runs headless. Dashboard is separate subpackage. |
| 5 | **No AI/LLM dependency** | Core engine is rule-based. LLM reasoner = optional plugin. |
| 6 | **Single entry point** | `python -m tie_v4` does everything. No multiple scripts. |
| 7 | **Dual trailing consolidation** | Merge TrailingManager + PositionMonitor → single executor (fix #38). Eliminate manual_trailing_v2. |
| 8 | **Halt flag** | `touch data/halt` stops trading. `rm data/halt` resumes. OS-agnostic. |
| 9 | **Day-start dual-write** | Persist to `data/` + `/tmp/`. Reads prefer persisted (fix #41). |
| 10 | **Gateway modify = full-replace** | Always send both `sl` AND `tp` to `/trade/modify` (fix #35). |
| 11 | **Single-threaded main loop** | Eliminates race conditions. Trading scans every 10s — no latency need. |
| 12 | **Dead code deletion** | 3172 → ~112 files. Knowledge graph, reasoning, compiler, SDK all removed. |
| 13 | **Per-strategy exit configs** | SemiHFT triggers BE faster than Bystra. Config-driven, not hardcoded. |
| 14 | **Volume key, not lot** | `OrderRequest.volume` everywhere. Adapter translates to broker-specific field. |
| 15 | **Entry zone = price range** | `{low: price-0.5, high: price+0.5}` — NEVER SL/TP values (fix #11). |

---

## 10. Bug Fixes Baked Into Architecture

These are NOT post-hoc patches. They are structural — the new architecture prevents these bugs by design.

| Bug # | Issue | Architectural Prevention |
|-------|-------|--------------------------|
| #11 | `entry_zone` filled with SL/TP | `Signal.entry_zone` docstring + validation: low/high must be within 5% of current price |
| #12 | ExitOrchestrator infers direction from SL/TP | `ExitOrchestrator.optimize(plan, direction=plan.action)` — explicit param, never infer |
| #13 | Session name `ASIAN` ≠ `ASIA` | Config YAML uses `ASIA`. Session rule reads from config. Single source. |
| #14 | `features.current_price` doesn't exist | `FeatureSnapshot` has NO `current_price` field. Price in `ScanContext.current_price` only. |
| #15 | `entry_zone={0,0}` | Strategy ABC requires entry_zone populated. Validation rejects {0,0}. |
| #16 | `_swing_pivot` returns 0 | Guard: `if pivot <= 0: return RiskPlan(valid=False)` |
| #17 | TP validation skips entry<=0 | Guard: `if entry <= 0 or tp == 0: return APPROVE (skip)` |
| #18 | Aggressive score weights wrong | Weights in config YAML, not hardcoded. Verified on startup. |
| #29 | Lot clipping (key mismatch) | `OrderRequest.volume` everywhere. `plan_to_decision()` maps correctly. |
| #34 | `risk_ctx["lot"]` hardcoded 0.02 | `risk_ctx.lot = decision.metadata["volume"]` — runtime value, never literal |
| #35 | Gateway modify needs BOTH sl AND tp | `BrokerAdapter.modify_order()` always sends both. Adapter-level guarantee. |
| #38 | Triple trailing systems | Single `TrailingManager`. No external `manual_trailing_v2.py`. |
| #39 | Shadow mode bypass | Eliminated. Trailing is internal to engine. |
| #40 | Crash-loop orphan PID | PID file + systemd only. Clean PID management in `__main__.py`. |
| #41 | Day-start wiped on VPS reboot | Dual-write to `data/` + `/tmp/`. Prefers persisted. |
| #44 | Non-TIE_ comment decode | `_COMMENT_STRAT_MAP` + raw comment fallback in dashboard. |
| #45 | Weekend reset bug | Hibernate logic checks `weekday() in (5, 6)` → skip reset. |
| #46 | SELL TP above entry | Post-planner direction guard in `tradeplan_adapter.py`. |
| #47 | Audit ≠ Execute | Engine has `--dry-run` flag. Separate concerns. |

---

## 11. Phase & Sprint Plan

### Overview

| Phase | Goal | Duration | Sprint Count | Key Risk |
|-------|------|----------|--------------|----------|
| **Phase 1** | Foundation — Folder structure, config, adapters | 2 weeks | 4 sprints | None |
| **Phase 2** | Core extraction — Features, regime, opportunity, rules | 2 weeks | 4 sprints | Logic drift |
| **Phase 3** | Strategy migration — Bystra, Aggressive, SemiHFT | 2 weeks | 4 sprints | Behavior change |
| **Phase 4** | Runtime — Engine loop, trailing, position monitor | 2 weeks | 4 sprints | Integration bugs |
| **Phase 5** | Dashboard + Observatory extraction | 1 week | 2 sprints | API mismatch |
| **Phase 6** | Testing + Validation | 1 week | 2 sprints | Regression |
| **Phase 7** | Deploy + Ship | 1 week | 2 sprints | Production cutover |
| **Total** | | **11 weeks** | **22 sprints** | |

---

### PHASE 1: Foundation (Week 1-2)

**Goal:** Package skeleton, config system, adapter pattern, zero-hardcode infrastructure.

#### Sprint 1.1 — Package Skeleton + Config (Day 1-3)

**Files created:**
```
tie_v4/
├── __init__.py
├── __main__.py
├── config.py
├── config/
│   └── engine.yaml
├── pyproject.toml
├── requirements.txt
├── Makefile
└── tests/
    ├── __init__.py
    └── test_config.py
```

**Deliverables:**
- [ ] `tie_v4/` folder structure (all `__init__.py` files)
- [ ] `pyproject.toml` with metadata, deps, entry point `tie_v4 = "tie_v4.__main__:main"`
- [ ] `config.py` — YAML loader + env var expansion (`${VAR}` syntax)
- [ ] `config/engine.yaml` — full default config (Section 7.1)
- [ ] `__main__.py` — argparse + config load + print resolved config
- [ ] `Makefile` — `make install`, `make run`, `make test`
- [ ] `requirements.txt` — core deps (pyyaml, requests)

**Acceptance:**
- `pip install -e .` succeeds
- `python -m tie_v4 --config config/engine.yaml` prints resolved config
- `${MT5_GATEWAY_URL}` resolves from env var
- `grep -rn "/home/ubuntu" tie_v4/` returns 0 matches
- `grep -rn "hardcoded" tie_v4/ --include="*.py"` returns 0 literal URL/path matches

**Tests:**
- `test_config.py` — YAML load, env var expansion, default values, missing file error, CLI override

---

#### Sprint 1.2 — Adapter Base + Mock (Day 4-6)

**Files created:**
```
tie_v4/
├── adapters/
│   ├── __init__.py
│   ├── base.py            # BrokerAdapter, MarketDataAdapter ABC
│   ├── models.py          # OrderRequest, OrderResponse, Position, AccountInfo, Candle, PriceQuote
│   ├── mt5_mock.py        # In-memory simulated broker
│   └── registry.py        # create_broker(config), create_market(config)
├── tests/
│   ├── test_mock_broker.py
│   ├── test_mock_market.py
│   └── test_registry.py
```

**Deliverables:**
- [ ] `adapters/base.py` — ABCs from Section 6.1
- [ ] `adapters/models.py` — All data models from Section 5.1
- [ ] `adapters/mt5_mock.py` — Full mock implementation (Section 6.2)
- [ ] `adapters/registry.py` — Auto-detect logic (Section 6.3)
- [ ] `requirements-dev.txt` — pytest, pytest-cov

**Acceptance:**
- Mock broker: `submit_order()` → in-memory position added, ticket returned
- Mock broker: `get_positions()` → returns mock positions
- Mock market: `get_candles("XAUUSD", "H1", 100)` → 100 fake candles with realistic OHLCV
- Mock market: `get_price("XAUUSD")` → PriceQuote with bid/ask/spread
- Registry: `create_broker({"broker": "mock"})` returns `MT5MockBroker`

**Tests:**
- `test_mock_broker.py` — submit, modify (both sl AND tp), close, get_positions, get_account
- `test_mock_market.py` — get_candles, get_price, get_spread
- `test_registry.py` — auto-detect mock, explicit mode selection

---

#### Sprint 1.3 — MT5 Gateway Adapter (Day 7-9)

**Files created:**
```
tie_v4/adapters/
├── mt5_gateway.py          # MT5GatewayBroker + MT5GatewayMarket
├── tests/
│   ├── test_gateway_adapter.py
│   └── test_gateway_integration.py  # Manual: against live gateway
```

**Source:** Extract + rewrite from `adapters/broker/mt5_broker.py` (179L)

**Deliverables:**
- [ ] `mt5_gateway.py` — `MT5GatewayBroker(BrokerAdapter)` + `MT5GatewayMarket(MarketDataAdapter)`
- [ ] All methods: submit_order, modify_order (full-replace: sl AND tp), close_position, get_positions, get_account, get_candles, get_price
- [ ] Error handling: timeout → retry 3x (exponential backoff 1s, 2s, 4s) → raise `AdapterError`
- [ ] SSL: `verify=False` for Cloudflare tunnel self-signed cert
- [ ] `config.py` update: parse `adapters.mt5_gateway` section

**Acceptance:**
- `MT5GatewayBroker(url, token).get_account()` returns real account data from production gateway
- `modify_order()` always sends both `sl` AND `tp` — test with `tp=None` → adapter reads current TP from `get_positions()`
- Timeout → retry 3x → fail with clear `AdapterError`
- Works with Cloudflare tunnel URL

**Tests:**
- `test_gateway_adapter.py` — mock HTTP responses (responses library), verify request payloads, retry logic
- `test_gateway_integration.py` — manual: `python -c "from tie_v4.adapters.mt5_gateway import ...; print(broker.get_account())"`

---

#### Sprint 1.4 — MT5 Native Adapter + Docker (Day 10-14)

**Files created:**
```
tie_v4/adapters/
├── mt5_native.py           # MT5NativeBroker + MT5NativeMarket
├── Dockerfile
├── requirements-win.txt
```

**Deliverables:**
- [ ] `mt5_native.py` — wraps `MetaTrader5` Python package
- [ ] All methods: submit_order, modify_order, close_position, get_positions, get_account, get_candles, get_price
- [ ] `requirements-win.txt` — `MetaTrader5>=5.0.45`
- [ ] `registry.py` update: auto-detect platform (`os.name` + MetaTrader5 availability)
- [ ] `Dockerfile` — base image, pip install, entry point

**Acceptance:**
- On Windows with MT5 installed: `MT5NativeBroker(login, password, server).get_account()` returns real data
- On Linux: graceful fallback to gateway adapter (no `ImportError`)
- Registry auto-detect: Windows + MT5 installed → native; Linux → gateway; `--dry-run` → mock

**Tests:**
- `test_native_adapter.py` — mock `MetaTrader5` module, verify call patterns
- `test_registry.py` — platform detection logic, fallback chain

---

### PHASE 2: Core Extraction (Week 3-4)

**Goal:** Extract pure logic from current codebase into `core/`. Zero external deps. All functions testable in isolation.

#### Sprint 2.1 — Features + Models (Day 15-17)

**Files created:**
```
tie_v4/core/
├── __init__.py
├── features/
│   ├── __init__.py
│   ├── engine.py           # FeatureEngine
│   └── models.py           # FeatureSnapshot dataclass
├── tests/
│   └── test_feature_engine.py
```

**Source:** Extract from `core/features/feature_engine.py` (354L) + `core/features/feature_models.py`

**Deliverables:**
- [ ] `models.py` — `FeatureSnapshot` dataclass (Section 5.1). ATR is `Dict[str, float]` not float.
- [ ] `engine.py` — `FeatureEngine.compute(candles: Dict[str, List[Candle]]) -> FeatureSnapshot`
- [ ] Fix: `features.atr` is dict `{tf: value}`, not float (pitfall from skill)
- [ ] Fix: NO `current_price` field on `FeatureSnapshot` (bug #14 prevention)

**Acceptance:**
- `FeatureEngine().compute(mock_candles)` returns valid `FeatureSnapshot`
- `snapshot.atr` is dict, `snapshot.atr.get('M5', 0.0)` works
- `hasattr(snapshot, 'current_price')` is False
- Pure Python — no external deps beyond stdlib + numpy (if needed)

**Tests:**
- `test_feature_engine.py` — edge cases: empty candles, single candle, all zeros, realistic M5 data

---

#### Sprint 2.2 — Regime + Opportunity (Day 18-20)

**Files created:**
```
tie_v4/core/
├── regime/
│   ├── __init__.py
│   ├── engine.py           # RegimeEngine
│   └── models.py           # Regime enum, RegimeSnapshot
├── opportunity/
│   ├── __init__.py
│   ├── engine.py           # OpportunityEngine
│   └── models.py           # OpportunitySnapshot, BlockReason
├── tests/
│   ├── test_regime.py
│   └── test_opportunity.py
```

**Source:** Extract from `core/regime/regime_engine.py`, `strategies/aggressive/regime/regime_engine.py`, `core/opportunity/opportunity_engine.py`

**Deliverables:**
- [ ] `regime/engine.py` — `RegimeEngine.detect(features) -> RegimeSnapshot`
- [ ] `regime/models.py` — `Regime` enum (TRENDING, RANGING, CHOPPY, LOW_LIQUIDITY)
- [ ] `opportunity/engine.py` — `OpportunityEngine.evaluate(features, regime, symbol) -> OpportunitySnapshot`
- [ ] `opportunity/models.py` — `OpportunitySnapshot`, `BlockReason` enum
- [ ] Session score logic: ASIA=25, LONDON=95, NEW_YORK=88, OVERLAP=98

**Acceptance:**
- Regime: correctly identifies TRENDING vs RANGING from features
- Opportunity: BLOCKED returns reason (session, spread, ATR out of range)
- Crypto (BTCUSD) skip: no EXHAUSTED/SLEEPING block for 24/7 symbols

**Tests:**
- `test_regime.py` — trending candle pattern → TRENDING, flat → RANGING
- `test_opportunity.py` — Asia session XAUUSD → score 25 (blocked), London → score 95

---

#### Sprint 2.3 — Context + Risk Rules (Day 21-23)

**Files created:**
```
tie_v4/core/
├── context/
│   ├── __init__.py
│   ├── engine.py           # ContextEngine
│   └── scan_context.py     # ScanContext dataclass
├── rules/
│   ├── __init__.py
│   ├── registry.py         # build_risk_registry(config) -> RiskRegistry
│   ├── sl_tp_validation.py # TPValidationRule
│   ├── spread_rule.py      # SpreadRule
│   ├── session_rule.py     # SessionRule
│   └── plugins/
│       ├── __init__.py
│       └── dynamic_lot.py  # _max_lot_for_equity(equity)
├── tests/
│   ├── test_risk_registry.py
│   ├── test_dynamic_lot.py
│   └── test_context.py
```

**Source:** Extract from `core/rules/risk/risk_registry.py`, `core/rules/risk/sl_tp_validation.py`, `core/rules/plugins/dynamic_lot.py`, `core/context/`

**Deliverables:**
- [ ] `context/engine.py` — `ContextEngine.build(price, candles, session) -> ScanContext`
- [ ] `context/scan_context.py` — `ScanContext` dataclass (Section 5.1)
- [ ] `rules/registry.py` — `build_risk_registry(config) -> RiskRegistry` with configurable rule chain
- [ ] `rules/sl_tp_validation.py` — TPValidationRule (fix #17: `entry <= 0` guard, fix #46: SELL TP direction)
- [ ] `rules/spread_rule.py` — SpreadRule with configurable max_points
- [ ] `rules/session_rule.py` — SessionRule with `allowed_sessions` from config
- [ ] `rules/plugins/dynamic_lot.py` — `_max_lot_for_equity(equity)` with tier boundaries

**Acceptance:**
- RiskRegistry: `evaluate(plan, ctx)` returns `RiskDecision(passed=True/False, reason=...)`
- allowed_sessions uses `\"ASIA\"` not `\"ASIAN\"` (fix #13) — from config
- TPValidation: SELL TP above entry → REJECT (fix #46)
- TPValidation: entry <= 0 → APPROVE (skip, fix #17)
- Lot: equity $300 → 0.01, $500 → 0.01 (flat <$2000), $2001 → 0.05

**Tests:**
- `test_risk_registry.py` — session filter, lot validation, TP validation, full gate chain
- `test_dynamic_lot.py` — all tier boundaries, edge cases
- `test_context.py` — SR level extraction, session derivation

---

#### Sprint 2.4 — Strategy Interfaces (Day 24-28)

**Files created:**
```
tie_v4/core/
├── strategy/
│   ├── __init__.py
│   ├── base.py             # BaseStrategy ABC
│   ├── result.py           # StrategyResult, TradePlan, TradeDecision, Signal
│   ├── exit_orchestrator.py # ExitOrchestrator
│   └── manager.py          # StrategyManager
├── tests/
│   ├── test_exit_orchestrator.py
│   └── test_strategy_manager.py
```

**Source:** Extract from `core/strategy/base_strategy.py`, `core/strategy/strategy_result.py`, `core/strategy/exit_orchestrator.py`, `core/strategy_manager/manager.py`

**Deliverables:**
- [ ] `base.py` — `BaseStrategy` ABC: `analyze(context: ScanContext, features: FeatureSnapshot) -> StrategyResult`
- [ ] `result.py` — All strategy models (Section 5.1)
- [ ] `exit_orchestrator.py` — `ExitOrchestrator.optimize(plan, direction=plan.action)` (fix #12: explicit direction)
- [ ] `manager.py` — `StrategyManager(strategies)` with config-driven enable/disable
- [ ] `TradePlan.metadata["strategy_code"]` → "B", "A", "S"

**Acceptance:**
- `BaseStrategy` ABC: `analyze(context, features) -> StrategyResult`
- `ExitOrchestrator.optimize()` takes explicit `direction` param, never infers from SL/TP
- `StrategyManager.run_all()` runs all enabled strategies, returns results
- Config: `strategies.aggressive.enabled: false` → aggressive skipped

**Tests:**
- `test_exit_orchestrator.py` — BUY widens TP down, SELL widens TP up, direction guard (fix #12)
- `test_strategy_manager.py` — mock strategy, verify run_all + enable/disable

---

### PHASE 3: Strategy Migration (Week 5-6)

**Goal:** Move Bystra, Aggressive, SemiHFT into `strategies/`. Preserve all logic, remove dead code.

#### Sprint 3.1 — Bystra Migration (Day 29-31)

**Files created:**
```
tie_v4/
├── strategies/
│   ├── __init__.py
│   └── bystra/
│       ├── __init__.py
│       ├── strategy.py      # BystraStrategy(BaseStrategy)
│       ├── config.py        # Configurable thresholds
│       └── metadata.py      # strategy_code="B", name="Bystra"
├── detectors/
│   ├── __init__.py
│   ├── common.py            # find_swing_pivots, find_nearest_support/resistance
│   ├── snrc1_detector.py
│   ├── snrc2_detector.py
│   ├── snrc3_detector.py
│   ├── qmc_detector.py
│   ├── qmm_detector.py
│   ├── qmr_detector.py
│   ├── qm2p_detector.py
│   ├── mother_candle_detector.py
│   ├── blindspot1_detector.py
│   ├── blindspot2_detector.py
│   ├── hybrid1_detector.py
│   ├── hybrid2_detector.py
│   ├── clab_detector.py
│   └── manipulation_detector.py
├── tests/
│   ├── test_bystra.py
│   └── test_detectors.py
```

**Source:** `strategies/bystra/strategy.py` (132L), `detectors/*.py` (1513L total)

**Deliverables:**
- [ ] `strategies/bystra/strategy.py` — `BystraStrategy(BaseStrategy)`
- [ ] All 14 detectors migrated, using H1 swing pivots for SR (danger zone fix)
- [ ] `detectors/common.py` — `find_swing_pivots()`, `find_nearest_support/resistance(candles, htf_candles=None)`
- [ ] `strategy_code="B"` → order comment `TIE_B_BUY`

**Acceptance:**
- `BystraStrategy.analyze(mock_context, mock_features)` returns valid `StrategyResult`
- All 14 detectors importable and callable
- `strategy_code="B"` → order comment `TIE_B_BUY`

**Tests:**
- `test_bystra.py` — mock candle patterns, verify detector triggers
- `test_detectors.py` — each detector with known pattern → expected signal

---

#### Sprint 3.2 — Aggressive Migration (Day 32-34)

**Files created:**
```
tie_v4/strategies/aggressive/
├── __init__.py
├── strategy.py              # AggressiveStrategy(BaseStrategy)
├── config.py
├── metadata.py              # strategy_code="A"
├── momentum_engine.py
├── velocity_engine.py
├── microstructure_engine.py
├── liquidity_engine.py
├── vwap_context_engine.py
├── opportunity_window.py
├── market_snapshot.py
├── entry_score_engine.py
├── regime/
│   ├── __init__.py
│   └── regime_engine.py
├── detectors/
│   ├── __init__.py
│   ├── compression_break.py
│   ├── liquidity_vacuum.py
│   ├── momentum_burst.py
│   ├── pullback_quality.py
│   ├── ribbon_ride.py
│   ├── velocity_spike.py
│   └── vwap_magnet.py
└── scoring/
    └── entry_scoring.py
```

**Source:** `strategies/aggressive/` (172L strategy.py + sub-engines)

**Deliverables:**
- [ ] `strategy.py` — `AggressiveStrategy(BaseStrategy)` (fix #14: use `context.current_price`, not `features.current_price`)
- [ ] All sub-engines migrated
- [ ] Fix #15: `entry_zone = {"low": price, "high": price}` (not {0,0})
- [ ] Fix #18: weights = momentum:0.30, velocity:0.25, micro:0.20, trend:0.15, liquidity:0.05, vwap:0.05
- [ ] Session filter: LONDON+NY+OVERLAP score ≥50, ASIA score 25

**Acceptance:**
- `AggressiveStrategy.analyze()` uses `context.current_price` (not `features.current_price`)
- `entry_zone` never {0,0}
- Weights match tuned values from fix #18

**Tests:**
- `test_aggressive.py` — price from context, entry_zone populated
- `test_entry_score.py` — weight verification

---

#### Sprint 3.3 — SemiHFT Migration (Day 35-37)

**Files created:**
```
tie_v4/strategies/semi_hft/
├── __init__.py
├── strategy.py              # SemiHFTStrategy(BaseStrategy)
├── config.py
├── metadata.py              # strategy_code="S"
├── entry_score.py           # MIN_ENTRY_SCORE=60
├── fast_risk.py             # _lot(equity), _swing_pivot()
├── daily_governor.py
├── tick_velocity_engine.py
├── volatility_engine.py
├── recovery_engine.py
├── opportunity_window.py
├── position_heat.py
├── micro_momentum_engine.py
├── market_pulse_engine.py
├── market_snapshot.py
├── liquidity_map.py
├── exit_intelligence.py
└── learning.py              # SQLite trade log
```

**Source:** `strategies/semi_hft/` (179L strategy.py + sub-engines)

**Deliverables:**
- [ ] `strategy.py` — `SemiHFTStrategy(BaseStrategy)`
- [ ] `entry_score.py` — MIN_ENTRY_SCORE=60 (from config)
- [ ] `fast_risk.py` — `_lot(equity)` (flat 0.01 for <$2000), `_swing_pivot()` with fix #16 guard
- [ ] All sub-engines migrated

**Acceptance:**
- `SemiHFTStrategy.analyze()` returns valid signal with entry_score ≥ 60
- `_lot(300)` returns 0.01, `_lot(500)` returns 0.01 (flat for <$2000)
- THRESHOLD=60 in both `entry_score_engine.py` and `semi_hft/entry_score.py`

**Tests:**
- `test_semi_hft.py` — entry score threshold, lot sizing
- `test_fast_risk.py` — lot tier boundaries, swing_pivot guard (fix #16)

---

#### Sprint 3.4 — Strategy Integration Test (Day 38-42)

**Files created:**
```
tie_v4/runtime/
├── __init__.py
├── multi_strategy.py        # MultiStrategyRuntime.fuse(results)
├── tradeplan_adapter.py     # plan_to_decision()
├── tests/
│   ├── test_multi_strategy.py
│   └── test_strategy_integration.py
```

**Source:** `runtime/multi_strategy_runtime.py` (109L), `runtime/adapters/tradeplan_adapter.py`

**Deliverables:**
- [ ] `multi_strategy.py` — `MultiStrategyRuntime.fuse(results)` — weighted fusion
- [ ] `tradeplan_adapter.py` — `plan_to_decision(plan) -> TradeDecision`
- [ ] Fix #46: post-planner direction guard in `plan_to_decision()`
- [ ] Strategy naming: `TIE_B_BUY`, `TIE_BA_SELL`, `TIE_BAS_BUY`
- [ ] Dedup logic: same direction within DEDUP_WINDOW → skip

**Acceptance:**
- `MultiStrategyRuntime.fuse()` correctly merges Bystra + Aggressive into BA_ setup
- Dedup: second signal within 120s of first → rejected
- `plan_to_decision()` applies direction guard: SELL tp < entry, BUY tp > entry
- All strategy codes map to correct order comments

**Tests:**
- `test_multi_strategy.py` — fusion logic, dedup, weighted scoring
- `test_strategy_integration.py` — mock market data → full pipeline (features → strategies → risk → decision)

---

### PHASE 4: Runtime (Week 7-8)

**Goal:** Wire everything into `TIEEngine`. Replace `tie_production.py`. Single process, single entry point.

#### Sprint 4.1 — Engine Core Loop (Day 43-45)

**Files created:**
```
tie_v4/runtime/
├── engine.py                # TIEEngine — main class
├── tests/
│   ├── test_engine.py
│   └── test_tradeplan_adapter.py
```

**Source:** `runtime/tie_production.py` (655L) — refactored into TIEEngine class

**Deliverables:**
- [ ] `engine.py` — `TIEEngine(broker, market, config)` with `run()` method
- [ ] Main loop: heartbeat → halt → hibernate → market check → scan → position monitor → sleep
- [ ] Lot injection: `fast_risk._lot(equity)` → `decision.metadata["volume"]` (fix #29)
- [ ] `risk_ctx.lot = decision.metadata.get("volume", 0.01)` — never hardcoded (fix #34)

**Acceptance:**
- `TIEEngine(dry_run=True).run()` — runs one scan cycle, no real trades
- Heartbeat written to `data/heartbeat.txt`
- `touch data/halt` → engine stops scanning
- Lot from strategy → risk_ctx matches (no hardcoded 0.02)

**Tests:**
- `test_engine.py` — halt flag, heartbeat, dry_run mode, hibernate logic
- `test_tradeplan_adapter.py` — lot injection, direction guard (fix #46)

---

#### Sprint 4.2 — Trailing Consolidation (Day 46-48)

**Files created:**
```
tie_v4/runtime/
├── trailing_manager.py      # Single trailing executor (consolidated)
├── contract_executor.py     # BE lock, trailing, partial TP, early exit
├── tests/
│   ├── test_trailing_manager.py
│   └── test_contract_executor.py
```

**Source:** `runtime/trailing_manager.py` + `runtime/contract_executor.py` (144L) + logic from `runtime/manual_trailing_v2.py`

**Deliverables:**
- [ ] `trailing_manager.py` — SINGLE trailing executor (consolidates TrailingManager + PositionMonitor + manual_trailing_v2)
- [ ] `contract_executor.py` — BE lock, trailing, partial TP, early exit
- [ ] Per-strategy exit configs (B/A/S profiles from config YAML)
- [ ] Fix #35: `modify_order()` always sends BOTH sl AND tp
- [ ] Fix #38: no duplicate trailing systems

**Acceptance:**
- Only ONE process modifies positions: `TrailingManager`
- `modify_order()` always sends `(sl, tp)` pair — never `(sl, None)` or `(None, tp)`
- Per-strategy trailing: SemiHFT (S) triggers BE at 0.15 ATR vs Bystra (B) at 0.5 ATR
- No external `manual_trailing_v2.py` script needed

**Tests:**
- `test_trailing_manager.py` — BE lock at ATR trigger, trail offset update
- `test_contract_executor.py` — partial TP, early exit, fix #35 (full-replace modify)

---

#### Sprint 4.3 — Position Monitor + Trade Tracker (Day 49-51)

**Files created:**
```
tie_v4/runtime/
├── position_monitor.py      # PositionMonitor(broker, trailing_manager)
├── trade_tracker.py         # TradeOutcomeTracker
├── governance/
│   ├── __init__.py
│   ├── daily_governor.py    # DailyProfitGovernorV2
│   └── trade_budget.py      # TradeBudgetManager
├── tests/
│   ├── test_position_monitor.py
│   ├── test_daily_governor.py
│   └── test_day_start.py
```

**Source:** `runtime/position_monitor.py` (75L), `runtime/trade_outcome_tracker.py`

**Deliverables:**
- [ ] `position_monitor.py` — `PositionMonitor(broker, trailing_manager)` — watches positions, triggers trailing
- [ ] `trade_tracker.py` — `TradeOutcomeTracker` — detects closed positions, logs win/loss to `data/wins.json`
- [ ] `governance/daily_governor.py` — `DailyProfitGovernorV2(daily_target)` with weekend guard
- [ ] `governance/trade_budget.py` — `TradeBudgetManager`
- [ ] Day-start dual-write: `data/day_start.json` + `/tmp/tie_day_start.json`
- [ ] Fix #41: reads prefer persisted over /tmp
- [ ] Fix #45: weekend guard (skip reset on Sat/Sun)

**Acceptance:**
- Position monitor: detects closed position → records win/loss
- Daily governor: profit >= target → hibernate 20min
- Day-start: dual-write on creation, restore from persisted on startup
- Weekend: no day-start reset on Saturday/Sunday

**Tests:**
- `test_position_monitor.py` — position appears/disappears → tracked
- `test_daily_governor.py` — target hit → hibernate
- `test_day_start.py` — dual-write, restore, weekend guard

---

#### Sprint 4.4 — Health Monitor + Service (Day 52-56)

**Files created:**
```
tie_v4/
├── runtime/
│   └── health_monitor.py    # HealthMonitor
├── scripts/
│   ├── install.sh           # pip install + systemd service setup
│   └── install.bat          # Windows Task Scheduler setup
├── tie-v4.service           # systemd service file
```

**Deliverables:**
- [ ] `runtime/health_monitor.py` — heartbeat, uptime, last scan time
- [ ] `scripts/install.sh` — pip install + systemd service installation
- [ ] `scripts/install.bat` — Windows Task Scheduler setup
- [ ] `tie-v4.service` — systemd service file
- [ ] `Makefile` update: `make service-install`, `make service-start`
- [ ] Fix #40: PID file management (clean up on exit, no orphan PIDs)

**systemd service file:**
```ini
[Unit]
Description=TIE V4 Portable Trading Engine
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/tie_v4
ExecStart=/opt/tie_v4/venv/bin/python -m tie_v4
Restart=on-failure
RestartSec=10
StandardOutput=append:/opt/tie_v4/logs/tie_v4.log
StandardError=append:/opt/tie_v4/logs/tie_v4.log

[Install]
WantedBy=multi-user.target
```

**Acceptance:**
- `make install` → pip install + systemd service installed
- `sudo systemctl start tie-v4` → engine running
- `sudo systemctl status tie-v4` → shows uptime, last heartbeat
- PID file cleaned on exit (no orphan PID)

**Tests:**
- `test_health_monitor.py` — heartbeat age, uptime calculation
- Manual: install on fresh VPS → engine starts → heartbeat current

---

### PHASE 5: Dashboard + Observatory (Week 9)

**Goal:** Extract dashboard and observatory into optional subpackages.

#### Sprint 5.1 — Observatory (Day 57-59)

**Files created:**
```
tie_v4/observatory/
├── __init__.py
├── gate_observatory.py      # GateObservatory (SQLite)
└── postmortem.py            # PostMortemAnalyzer
```

**Source:** `runtime/gate_observatory.py`

**Deliverables:**
- [ ] `gate_observatory.py` — `GateObservatory(db_path: str)` — record decisions, query recent
- [ ] `postmortem.py` — `PostMortemAnalyzer` — analyze closed trades
- [ ] DB schema: `gate_decisions`, `decision_traces` tables
- [ ] Fix: filter by timestamp (DB cumulative, not reset on restart)

**SQLite Schema:**
```sql
CREATE TABLE IF NOT EXISTS gate_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    symbol TEXT NOT NULL,
    direction TEXT,
    strategy_code TEXT,
    score REAL,
    passed INTEGER NOT NULL,  -- 1=PASS, 0=FAIL
    reason TEXT,
    entry REAL,
    sl REAL,
    tp REAL,
    lot REAL
);

CREATE TABLE IF NOT EXISTS decision_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gate_decision_id INTEGER REFERENCES gate_decisions(id),
    rule_name TEXT NOT NULL,
    passed INTEGER NOT NULL,
    reason TEXT,
    details TEXT  -- JSON
);

CREATE INDEX IF NOT EXISTS idx_gate_timestamp ON gate_decisions(timestamp);
CREATE INDEX IF NOT EXISTS idx_traces_decision ON decision_traces(gate_decision_id);
```

**Acceptance:**
- `GateObservatory.record(decision, plan)` → SQLite entry
- `query_recent(minutes=2)` → only recent entries (not historical from past restarts)
- DB created on first run, schema auto-migrate

**Tests:**
- `test_gate_observatory.py` — record, query, timestamp filter, schema creation

---

#### Sprint 5.2 — Dashboard (Day 60-63)

**Files created:**
```
tie_v4/dashboard/
├── __init__.py
├── server.py                # FastAPI app
├── routers/
│   └── dashboard.py         # All API endpoints
├── static/
│   ├── index.html
│   ├── app.js
│   └── style.css
```

**Source:** Dashboard code from current port 3002 backend + frontend

**Deliverables:**
- [ ] `server.py` — FastAPI app with static file serving
- [ ] `routers/dashboard.py` — all API endpoints (Section 13)
- [ ] `static/` — index.html, app.js, style.css (migrated from current)
- [ ] Real-time gateway data via `_gw_fetch()` helper
- [ ] Strategy decode with `_COMMENT_STRAT_MAP` (fix #44)
- [ ] Session derive client-side (fix #25)
- [ ] Performance from gate_observatory.db (fix #26)
- [ ] Win rate from trade_tracker

**Acceptance:**
- `python -m tie_v4.dashboard` → dashboard at localhost:3002
- `/api/dashboard` returns real-time equity from gateway
- `/api/positions` shows strategy + setup columns
- Session header shows correct session from UTC hour

**Tests:**
- `test_dashboard_api.py` — mock gateway, verify all endpoints
- Manual: curl all endpoints, compare with gateway data

---

### PHASE 6: Testing + Validation (Week 10)

**Goal:** Regression test. Verify V4 Portable produces identical results to current production.

#### Sprint 6.1 — Unit + Integration Tests (Day 64-67)

**Deliverables:**
- [ ] Unit tests for ALL core modules (features, regime, opportunity, context, rules, strategy)
- [ ] Integration test: mock market data → full pipeline → verify decision
- [ ] Adapter tests: mock, gateway (with recorded responses)
- [ ] Test coverage report: target >80% for core/

**Acceptance:**
- `pytest` passes all tests
- `pytest --cov=core/` shows >80% coverage
- No regressions from current behavior

---

#### Sprint 6.2 — Regression + Dry-Run (Day 68-70)

**Deliverables:**
- [ ] Dry-run test: `python -m tie_v4 --dry-run` against live gateway
- [ ] Compare decisions: V4 Portable vs V4 Production (same market data, same results)
- [ ] Performance benchmark: scan cycle < 5s (target)
- [ ] Memory test: engine runs 24h without memory leak

**Acceptance:**
- Dry-run: engine scans, logs decisions, no real trades
- Decision match: same signal direction, SL, TP, lot as production
- Memory: RSS stable after 24h (< 200MB)

---

### PHASE 7: Deploy + Ship (Week 11)

**Goal:** Production cutover. Old `tie_production.py` → new `python -m tie_v4`.

#### Sprint 7.1 — Staging Deploy (Day 71-73)

**Deliverables:**
- [ ] Deploy V4 Portable to staging VPS (separate from production)
- [ ] Run with real gateway, real market data, but `dry_run=True`
- [ ] Monitor 48h: decisions, memory, stability
- [ ] Fix any issues found

**Acceptance:**
- Staging runs 48h without crash
- All decisions logged correctly
- No memory leak

---

#### Sprint 7.2 — Production Cutover (Day 74-77)

**Deliverables:**
- [ ] Stop old `tie-production.service`
- [ ] Close all open positions
- [ ] Install V4 Portable as `tie-v4.service`
- [ ] Start with real money
- [ ] Monitor 24h: trades executed, trailing working, dashboard live
- [ ] Update README.md with quick-start guide
- [ ] CHANGELOG.md

**Acceptance:**
- `sudo systemctl start tie-v4` → engine running
- First trade executed correctly
- Dashboard shows real-time data
- No hardcoded paths in any source file

**Rollback plan:**
1. Stop `tie-v4.service`
2. Start old `tie-production.service`
3. Old code still in `/home/ubuntu/trading-intelligence-engine/`

---

## 12. Migration Map (Old → New)

### 12.1 File-by-File Mapping

| Current File | Lines | New File | Notes |
|-------------|-------|----------|-------|
| `runtime/tie_production.py` | 655 | `runtime/engine.py` | Refactored into class |
| `runtime/multi_strategy_runtime.py` | 109 | `runtime/multi_strategy.py` | |
| `runtime/contract_executor.py` | 144 | `runtime/contract_executor.py` | |
| `runtime/position_monitor.py` | 75 | `runtime/position_monitor.py` | |
| `runtime/trailing_manager.py` | ? | `runtime/trailing_manager.py` | Absorbs manual_trailing_v2 |
| `runtime/manual_trailing_v2.py` | ? | DELETED | Absorbed into trailing_manager |
| `runtime/manual_trailing.py` | ? | DELETED | Legacy, absorbed |
| `runtime/trade_outcome_tracker.py` | ? | `runtime/trade_tracker.py` | |
| `runtime/tradeplan_adapter.py` | ? | `runtime/tradeplan_adapter.py` | |
| `runtime/gate_observatory.py` | ? | `observatory/gate_observatory.py` | |
| `runtime/health_monitor.py` | ? | `runtime/health_monitor.py` | |
| `runtime/telegram_notifier.py` | ? | OPTIONAL | Not in core package |
| `runtime/adaptive_learning.py` | ? | DELETED | Stub |
| `runtime/auto_optimizer.py` | ? | DELETED | Unused |
| `runtime/backtest_engine.py` | ? | EXCLUDED | Separate project |
| `runtime/compiler_bridge.py` | ? | DELETED | Dead |
| `runtime/context_builder.py` | ? | Merged into `core/context/engine.py` | |
| `runtime/dispatcher.py` | ? | DELETED | Dead |
| `runtime/entry_monitor.py` | ? | DELETED | Disabled in production |
| `runtime/events.py` | ? | DELETED | Unused event system |
| `runtime/exceptions.py` | ? | `runtime/exceptions.py` | Keep |
| `runtime/execution_analytics.py` | ? | DELETED | Unused |
| `runtime/execution_result.py` | ? | `adapters/models.py` | Merged |
| `runtime/execution_runtime.py` | ? | DELETED | Dead |
| `runtime/execution_service.py` | ? | DELETED | Dead |
| `runtime/hck_wire.py` | ? | DELETED | HCK bridge dead |
| `runtime/health.py` | ? | Merged into health_monitor.py | |
| `runtime/learning_brain.py` | ? | DELETED | Stub |
| `runtime/live_trading.py` | ? | DELETED | Replaced by engine.py |
| `runtime/monte_carlo_replay.py` | ? | EXCLUDED | Separate project |
| `runtime/orchestrator.py` | ? | DELETED | Dead |
| `runtime/order_converter.py` | ? | Merged into adapter | |
| `runtime/portfolio_intelligence.py` | ? | DELETED | Unused |
| `runtime/position_manager.py` | ? | DELETED | Replaced by position_monitor |
| `runtime/position_state.py` | ? | Merged into position_monitor | |
| `runtime/registry.py` | ? | DELETED | Unused |
| `runtime/runtime_events.py` | ? | DELETED | Unused |
| `runtime/runtime_logger.py` | ? | Merged into logging_config | |
| `runtime/runtime.py` | ? | DELETED | Replaced by engine.py |
| `runtime/state.py` | ? | DELETED | In-memory state in engine |
| `runtime/tie_ws_server.py` | ? | DELETED | WebSocket server unused |
| `runtime/trade_journal.py` | ? | OPTIONAL | Separate module |
| `runtime/trade_postmortem.py` | ? | `observatory/postmortem.py` | |
| `runtime/trading_intelligence.py` | ? | DELETED | Dead |
| `adapters/broker/mt5_broker.py` | 179 | `adapters/mt5_gateway.py` | Rewritten |
| `core/features/feature_engine.py` | 354 | `core/features/engine.py` | Cleaned |
| `core/features/feature_models.py` | ? | `core/features/models.py` | |
| `core/regime/regime_engine.py` | ? | `core/regime/engine.py` | |
| `core/opportunity/opportunity_engine.py` | ? | `core/opportunity/engine.py` | |
| `core/context/context_engine.py` | ? | `core/context/engine.py` | |
| `core/context/scan_context.py` | ? | `core/context/scan_context.py` | |
| `core/rules/risk/risk_registry.py` | 40 | `core/rules/registry.py` | |
| `core/rules/risk/sl_tp_validation.py` | ? | `core/rules/sl_tp_validation.py` | |
| `core/rules/plugins/dynamic_lot.py` | ? | `core/rules/plugins/dynamic_lot.py` | |
| `core/strategy/base_strategy.py` | ? | `core/strategy/base.py` | |
| `core/strategy/strategy_result.py` | ? | `core/strategy/result.py` | |
| `core/strategy/exit_orchestrator.py` | ? | `core/strategy/exit_orchestrator.py` | |
| `strategies/bystra/*` | ~300 | `strategies/bystra/` | All files |
| `strategies/aggressive/*` | ~500 | `strategies/aggressive/` | All files |
| `strategies/semi_hft/*` | ~500 | `strategies/semi_hft/` | All files |
| `detectors/*` | 1513 | `detectors/` | All 14 detectors |

### 12.2 Dead Code Elimination Summary

| Category | Current Files | Status |
|----------|--------------|--------|
| Knowledge graph (`core/knowledge/`, `core/graph/`, `core/query/`) | ~30 | DELETE |
| Reasoning engine (`core/reasoning/`, `core/explanation/`) | ~20 | DELETE |
| Compiler system (`core/compiler/`, `core/facts/`, `core/patterns/`) | ~25 | DELETE |
| Compatibility layer (`core/compatibility/`, `core/compat/`) | ~10 | DELETE |
| Validators (`core/validator/`, `core/schema/`) | ~10 | DELETE |
| Learning/lifecycle (`core/learning/`, `core/lifecycle/`) | ~5 | DELETE |
| Decision pipeline (`core/decision/`) | ~15 | DELETE (replaced by simpler flow) |
| Setup engine (`core/setup/`) | ~15 | DELETE |
| Signals/registry/relationships (`core/signals/`, `core/registry/`, `core/relationships/`) | ~10 | DELETE |
| SDK (`sdk/`) | ~20+ | DELETE |
| Vibe-Trading (`Vibe-Trading/`) | ~100+ | DELETE |
| Knowledge base (`knowledge/`) | ~50+ | DELETE |
| Dead runtime modules | ~15 | DELETE |
| **TOTAL DELETED** | **~325+ files** | |

---

## 13. API Specifications

### 13.1 Dashboard Endpoints

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/dashboard` | Main dashboard data | `{equity, balance, daily_pnl, positions_count, floating_pnl, target_hit}` |
| GET | `/api/positions` | Open positions list | `[{ticket, symbol, strategy, setup, direction, volume, entry, sl, tp, profit}]` |
| GET | `/api/scores` | Strategy scores breakdown | `{bystra: {score, weight}, aggressive: {...}, semi_hft: {...}}` |
| GET | `/api/strategies` | Strategy enable/disable state | `{bystra: {enabled, weight}, ...}` |
| GET | `/api/engine/health` | Engine health status | `{status, last_scan, last_error, uptime}` |
| GET | `/api/performance/daily` | Daily performance stats | `{trades, wins, losses, win_rate, profit}` |

### 13.2 Gateway Endpoints (External — MT5 Bridge)

| Method | Path | Description | Notes |
|--------|------|-------------|-------|
| GET | `/account` | Account info | Returns `{balance, equity, margin, free_margin, profit}` |
| GET | `/account/positions` | Open positions | Returns array of position objects |
| GET | `/trade/candles/{symbol}` | Candle data | Query params: `tf=H1&count=250` |
| POST | `/trade` | Submit order | Body: `{symbol, direction, volume, sl, tp, comment}` |
| POST | `/trade/modify` | Modify SL/TP | Body: `{ticket, sl, tp}` — BOTH required (422 if missing) |
| POST | `/trade/close/{ticket}` | Close position | Path param: ticket |

---

## 14. Database Schemas

### 14.1 Gate Observatory (SQLite)

```sql
-- Gate decisions — every risk gate evaluation
CREATE TABLE IF NOT EXISTS gate_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    symbol TEXT NOT NULL,
    direction TEXT,
    strategy_code TEXT,
    score REAL,
    passed INTEGER NOT NULL,  -- 1=PASS, 0=FAIL
    reason TEXT,
    entry REAL,
    sl REAL,
    tp REAL,
    lot REAL
);

-- Decision traces — per-rule breakdown
CREATE TABLE IF NOT EXISTS decision_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gate_decision_id INTEGER REFERENCES gate_decisions(id),
    rule_name TEXT NOT NULL,
    passed INTEGER NOT NULL,
    reason TEXT,
    details TEXT  -- JSON blob
);

CREATE INDEX IF NOT EXISTS idx_gate_timestamp ON gate_decisions(timestamp);
CREATE INDEX IF NOT EXISTS idx_traces_decision ON decision_traces(gate_decision_id);
```

### 14.2 Trade Tracker (JSON — data/wins.json)

```json
{
  "wins": 12,
  "losses": 8,
  "total": 20,
  "last_updated": "2026-08-06T14:30:15Z"
}
```

### 14.3 Day Start (JSON — data/day_start.json)

```json
{
  "balance": 350.0,
  "date": "2026-08-06"
}
```

---

## 15. Risk Matrix

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Strategy logic drift during extraction | HIGH | MEDIUM | Side-by-side diff, integration tests, regression dry-run |
| Gateway API changes | MEDIUM | LOW | Adapter abstracts gateway; mock adapter for tests |
| Windows MT5 package incompatible | MEDIUM | MEDIUM | Mock adapter fallback; test early (Sprint 1.4) |
| Memory leak in main loop | HIGH | LOW | 24h soak test in Phase 6 |
| Dashboard breaks during extraction | LOW | HIGH | Dashboard is optional; engine works without it |
| Production cutover fails | HIGH | LOW | Rollback plan; old code preserved |
| Dead code deletion removes needed logic | MEDIUM | LOW | Full grep audit before deletion; git history preserved |
| Config validation misses bad values | MEDIUM | MEDIUM | Schema validation on startup; test edge cases |

---

## 16. Dependencies

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
responses>=0.23    # HTTP mocking for gateway tests
```

---

## 17. Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| **Zero hardcoded paths** | 0 matches | `grep -rn "/home/ubuntu" tie_v4/` |
| **Install success** | Linux + Windows | `pip install .` on both |
| **Regression pass** | 100% decision match | Side-by-side dry-run comparison |
| **Scan cycle time** | < 5s | Benchmark in Phase 6 |
| **Memory (24h)** | < 200MB RSS | `ps -o rss -p $(pgrep -f tie_v4)` |
| **Test coverage** | > 80% core/ | `pytest --cov=core/` |
| **File count** | ~112 files | `find tie_v4/ -type f | wc -l` |
| **Line count** | < 8000 lines | `find tie_v4/ -name "*.py" | xargs wc -l` |
| **Dead code ratio** | < 5% unused | No function without caller |
| **Startup time** | < 3s | Time from `python -m tie_v4` to first heartbeat |

---

## 18. Out of Scope (ponytail)

| Item | Why Skipped | When to Add |
|------|-------------|-------------|
| Backtest module | Separate project, not production | When backtesting needed |
| Vibe-Trading integration | Dead code | Never (remove from codebase) |
| Knowledge graph / reasoning | Unused | When LLM trading needed |
| SDK / compiler / pack system | Unused | When multi-asset ecosystem |
| Skills / learning engine | Stub only | When ML-based adaptation needed |
| HCK bridge | Current-setup specific | When multi-agent needed |
| Multi-symbol optimization | Single XAUUSD now | When scaling to 5+ pairs |
| Telegram notifier | Optional, not core | When alert system needed |
| Monte Carlo replay | Separate analysis tool | When backtesting framework built |

---

## 19. Glossary

| Term | Definition |
|------|-----------|
| **Adapter** | Platform-specific implementation of Broker or Market interface |
| **Bystra** | Swing/trend strategy with 14 pattern detectors (C5/C6) |
| **Aggressive** | Scalping strategy with momentum/velocity engines (C7) |
| **SemiHFT** | High-frequency strategy with microstructure detection (C8) |
| **Risk Gate** | Collection of rules that approve/reject trade plans |
| **Trailing Manager** | Single consolidated system for BE lock + trailing + partial TP |
| **Halt Flag** | File-based stop mechanism (`touch data/halt`) |
| **Day-Start** | Account balance at start of trading day (for daily PnL calc) |
| **Hibernate** | Engine sleep mode when daily profit target reached |
| **Gate Observatory** | SQLite DB recording all risk gate decisions |
| **Fusion** | Process of merging signals from multiple strategies into single trade plan |
| **Dual-write** | Writing state to both persistent (`data/`) and fast-access (`/tmp/`) locations |
| **Full-replace** | Gateway modify endpoint requires both SL and TP — never partial update |

---

---

## 20. Sprint Dependency Graph

Text-based dependency diagram. Arrows indicate blocking relationships. Sprints at the same indent without arrows between them can run in parallel.

```
Phase 1: Foundation
  Sprint 1.1 [Package skeleton + config]
      |
      +---> Sprint 1.2 [Adapter mock]
      |         |
      |         +---> Sprint 1.3 [Gateway adapter]  ──────────────────────┐
      |         |                                                          |
      |         +---> Sprint 1.4 [CLI + daemon]                           |
      |         |                                                          |
      |         +---> Sprint 2.1 [Feature engineering]                     |
      |                   |                                                |
      |                   +---> Sprint 2.2 [Detector framework]            |
      |                   |                                                |
      |                   +---> Sprint 2.3 [Risk rules]                    |
      |                             |                                      |
      |                             +---> Sprint 2.4 [Strategy interfaces] |
      |                                       |                            |
      |                   ┌───────────────────┼────────────────────┐       |
      |                   │                   │                    │       |
Phase 3: Strategies ──────┤                   │                    │       |
      |                   │                   │                    │       |
      |     Sprint 3.1 [Bystra]               │                    │       |
      |     Sprint 3.2 [Aggressive]           │                    │       |
      |     Sprint 3.3 [SemiHFT]              │                    │       |
      |                   │                   │                    │       |
      |                   └───┬───────────────┘────────────────────┘       |
      |                       │                                            |
      |              Sprint 3.4 [Integration test]                         |
      |                       │                                            |
Phase 4: Engine ─────────────┼─────────────────────────────────────────────┘
      |                       │                                            │
      |              Sprint 4.1 [Engine core] <──── needs 2.4 + 3.4 + 1.3
      |                       |
      |              Sprint 4.2 [Trailing manager]
      |                       |
      |              Sprint 4.3 [State persistence]
      |                       |
      |              Sprint 4.4 [Gate observatory]
      |
Phase 5: Dashboard ───────── (independent of Phase 4, can parallel)
      |
      Sprint 5.1 [FastAPI dashboard]
                  |
                  Sprint 5.2 [WebSocket live updates]

Phase 6: Integration
      Sprint 6.1 [End-to-end integration] <── needs all Phase 1-5
                  |
                  Sprint 6.2 [Performance tuning]
                              |
                              Sprint 6.3 [Monitoring + alerts]

Phase 7: Deployment
      Sprint 7.1 [Packaging + systemd]
                  |
                  Sprint 7.2 [Migration + cutover]
```

### Parallelization Summary

| Window | Sprints That Can Run Concurrently | Blocked By |
|--------|----------------------------------|------------|
| W1 | 1.1 only | — |
| W2 | 1.2 | 1.1 |
| W3 | 1.3, 1.4, 2.1 | 1.2 |
| W4 | 2.2, 2.3 | 2.1 |
| W5 | 2.4 | 2.3 |
| W6 | 3.1, 3.2, 3.3 | 2.4 |
| W7 | 3.4 | 3.1 + 3.2 + 3.3 |
| W8 | 4.1 | 2.4 + 3.4 + 1.3 |
| W9 | 4.2 | 4.1 |
| W10 | 4.3 | 4.2 |
| W11 | 4.4, 5.1 | 4.3 |
| W12 | 5.2 | 5.1 |
| W13 | 6.1 | all Phase 1-5 |
| W14 | 6.2 | 6.1 |
| W15 | 6.3 | 6.2 |
| W16 | 7.1 | 6.3 |
| W17 | 7.2 | 7.1 |

> **Critical path:** 1.1 → 1.2 → 2.1 → 2.3 → 2.4 → 3.1/3.2/3.3 → 3.4 → 4.1 → 4.2 → 4.3 → 4.4 → 6.1 → 6.2 → 6.3 → 7.1 → 7.2 (17 windows sequential worst case). With parallelization in W3/W6/W11, compressible to ~13 windows.

---

## 21. Effort Estimates

### Per-Sprint Breakdown

| Sprint | Name | Coding | Testing | Docs | Total |
|--------|------|--------|---------|------|-------|
| 1.1 | Package skeleton + config | 6h | 2h | 2h | 10h |
| 1.2 | Adapter mock | 8h | 4h | 2h | 14h |
| 1.3 | Gateway adapter | 10h | 4h | 2h | 16h |
| 1.4 | CLI + daemon | 8h | 4h | 2h | 14h |
| 2.1 | Feature engineering | 10h | 6h | 2h | 18h |
| 2.2 | Detector framework | 8h | 6h | 2h | 16h |
| 2.3 | Risk rules | 10h | 6h | 2h | 18h |
| 2.4 | Strategy interfaces | 8h | 6h | 2h | 16h |
| 3.1 | Bystra strategy | 10h | 6h | 2h | 18h |
| 3.2 | Aggressive strategy | 8h | 4h | 2h | 14h |
| 3.3 | SemiHFT strategy | 8h | 4h | 2h | 14h |
| 3.4 | Integration test | 4h | 10h | 2h | 16h |
| 4.1 | Engine core | 12h | 6h | 2h | 20h |
| 4.2 | Trailing manager | 8h | 6h | 2h | 16h |
| 4.3 | State persistence | 6h | 4h | 2h | 12h |
| 4.4 | Gate observatory | 6h | 4h | 2h | 12h |
| 5.1 | FastAPI dashboard | 10h | 4h | 2h | 16h |
| 5.2 | WebSocket live updates | 8h | 4h | 2h | 14h |
| 6.1 | End-to-end integration | 6h | 10h | 2h | 18h |
| 6.2 | Performance tuning | 8h | 4h | 2h | 14h |
| 6.3 | Monitoring + alerts | 6h | 4h | 2h | 12h |
| 7.1 | Packaging + systemd | 8h | 4h | 2h | 14h |
| 7.2 | Migration + cutover | 6h | 6h | 4h | 16h |

### Phase Totals

| Phase | Sprints | Coding | Testing | Docs | Total |
|-------|---------|--------|---------|------|-------|
| 1. Foundation | 1.1–1.4 | 32h | 14h | 8h | 54h |
| 2. Core Logic | 2.1–2.4 | 36h | 24h | 8h | 68h |
| 3. Strategies | 3.1–3.4 | 30h | 26h | 8h | 64h |
| 4. Engine | 4.1–4.4 | 32h | 20h | 8h | 60h |
| 5. Dashboard | 5.1–5.2 | 18h | 8h | 4h | 30h |
| 6. Integration | 6.1–6.3 | 20h | 18h | 6h | 44h |
| 7. Deployment | 7.1–7.2 | 14h | 10h | 6h | 30h |
| **Grand Total** | **22 sprints** | **182h** | **120h** | **48h** | **~350h** |

> **Note:** Estimates assume single developer. With 2 developers on parallelizable sprints (W3, W6, W11), wall-clock time reduces ~30%. Realistic wall-clock: 220–280h (accounting for overlap, code review, iteration).

### Effort Distribution

```
Coding:   ████████████████████████████████████████  52%
Testing:  ██████████████████████████████            34%
Docs:     ██████████████                            14%
```

---

## 22. Config Validation Schema

Pydantic v2 models for `config/engine.yaml` validation. All models use `model_config = ConfigDict(extra="forbid")` to reject unknown keys.

```python
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
import os, re

# --- Env var expansion ---

_ENV_PATTERN = re.compile(r'\$\{(\w+)(?::([^}]*))?\}')

def expand_env(value: str) -> str:
    """Expand ${VAR} and ${VAR:default} in string values."""
    def _replace(m):
        var, default = m.group(1), m.group(2)
        return os.environ.get(var, default if default is not None else '')
    return _ENV_PATTERN.sub(_replace, value)


# --- Sub-models ---

class BrokerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adapter: str = Field(..., pattern="^(mock|gateway)$")
    host: str = "127.0.0.1"
    port: int = Field(18808, ge=1024, le=65535)
    magic: int = Field(202608, ge=1)
    login: Optional[str] = None          # env-expanded
    password: Optional[str] = None       # env-expanded

    @field_validator('login', 'password', mode='before')
    @classmethod
    def _expand(cls, v):
        return expand_env(v) if isinstance(v, str) else v


class TrailingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = Field("atr", pattern="^(atr|fixed|step)$")
    atr_period: int = Field(14, ge=1, le=100)
    atr_multiplier: float = Field(1.5, gt=0, le=10.0)
    breakeven_after_r: float = Field(1.0, gt=0, le=5.0)
    breakeven_buffer_points: int = Field(10, ge=0)
    partial_tp_r_levels: list[float] = Field(default=[1.0, 2.0])
    partial_tp_pcts: list[float] = Field(default=[0.5, 0.3])


class RiskConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily_target_pct: float = Field(3.0, gt=0, le=20.0)
    daily_max_loss_pct: float = Field(5.0, gt=0, le=30.0)
    max_concurrent_positions: int = Field(3, ge=1, le=10)
    max_lot: float = Field(0.05, gt=0, le=1.0)
    min_lot: float = Field(0.01, gt=0, le=1.0)
    max_spread_points: int = Field(50, ge=1, le=500)
    cooldown_after_loss_seconds: int = Field(300, ge=0)
    halt_on_api_error: bool = True
    trailing: TrailingConfig = TrailingConfig()

    @model_validator(mode='after')
    def _lot_order(self):
        if self.min_lot > self.max_lot:
            raise ValueError(f"min_lot ({self.min_lot}) > max_lot ({self.max_lot})")
        return self


class StrategyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., pattern="^(bystra|aggressive|semihft|custom)$")
    enabled: bool = True
    detectors: list[str] = Field(default_factory=lambda: ["all"])
    scan_interval_seconds: int = Field(30, ge=5, le=300)
    min_confluence_score: float = Field(0.6, ge=0, le=1.0)
    symbols: list[str] = Field(default=["XAUUSD"])
    timeframes: list[str] = Field(default=["M5", "H1"])


class DashboardConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = Field(8080, ge=1024, le=65535)
    websocket_enabled: bool = True
    refresh_interval_ms: int = Field(1000, ge=100, le=30000)


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: str = Field("INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    file: str = "logs/tie-engine.log"
    max_size_mb: int = Field(50, ge=1, le=1000)
    backup_count: int = Field(5, ge=1, le=100)
    console: bool = True
    json_format: bool = False


class EngineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = "4.0.0"
    broker: BrokerConfig
    strategy: StrategyConfig = StrategyConfig()
    risk: RiskConfig = RiskConfig()
    dashboard: DashboardConfig = DashboardConfig()
    logging: LoggingConfig = LoggingConfig()
    data_dir: str = "data"
    halt_file: str = "data/halt"

    @field_validator('data_dir', 'halt_file', mode='before')
    @classmethod
    def _expand_paths(cls, v):
        return expand_env(v) if isinstance(v, str) else v
```

### CLI Override Support

```bash
# Override any nested key via --set dotpath=value
tie-engine run --set broker.adapter=mock --set risk.max_lot=0.02

# Implementation in CLI layer:
def apply_overrides(config: EngineConfig, overrides: list[str]) -> EngineConfig:
    data = config.model_dump()
    for override in overrides:
        key, value = override.split('=', 1)
        parts = key.split('.')
        target = data
        for p in parts[:-1]:
            target = target[p]
        # Type coercion: try int, float, bool, else string
        try:
            value = int(value)
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                value = value.lower() in ('true', '1', 'yes')
                if not value and value != False:
                    value = override.split('=', 1)[1]  # keep as string
        target[parts[-1]] = value
    return EngineConfig.model_validate(data)
```

### Validation Rules Summary

| Field | Rule | Rationale |
|-------|------|-----------|
| `broker.adapter` | enum: mock, gateway | Only two supported adapters |
| `broker.port` | 1024–65535 | Valid port range |
| `risk.daily_target_pct` | > 0, ≤ 20% | Positive target, sane max |
| `risk.daily_max_loss_pct` | > 0, ≤ 30% | Must have loss limit |
| `risk.max_lot` | > 0, ≤ 1.0 | Account safety cap |
| `risk.min_lot ≤ risk.max_lot` | cross-field | Logical ordering |
| `strategy.scan_interval_seconds` | ≥ 5 | Prevent API spam |
| `strategy.min_confluence_score` | 0–1 | Normalized score range |
| `dashboard.port` | 1024–65535 | Valid port range |
| `logging.level` | enum: DEBUG…CRITICAL | Standard Python levels |

---

## 23. Testing Strategy

### Test Architecture

```
tests/
├── conftest.py                  # Shared fixtures
├── fixtures/
│   ├── candles.py               # Mock candle generators
│   ├── accounts.py              # Mock account/position factories
│   └── market_data.py           # Realistic XAUUSD patterns
├── unit/
│   ├── test_core_features.py
│   ├── test_core_detectors.py
│   ├── test_core_risk.py
│   ├── test_core_trailing.py
│   └── test_core_state.py
├── integration/
│   ├── test_pipeline_flow.py
│   ├── test_engine_loop.py
│   └── test_state_persistence.py
├── adapter/
│   ├── test_mock_adapter.py
│   └── test_gateway_adapter.py
├── regression/
│   ├── test_v4_parity.py        # Same inputs → same decisions
│   └── test_performance.py      # No regression vs baseline
└── strategies/
    ├── test_bystra.py
    ├── test_aggressive.py
    └── test_semihft.py
```

### Test Naming Convention

```
test_{module}_{scenario}_{expected}

Examples:
test_risk_daily_limit_exceeded_blocks_trade
test_trailing_breakeven_locks_at_1r
test_detector_fvg_bullish_detects_gap
test_engine_halt_flag_skips_scan
test_adapter_gateway_timeout_retries
```

### Core pytest Fixtures

```python
# tests/conftest.py
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
import numpy as np

@pytest.fixture
def mock_broker():
    """MockBrokerAdapter with configurable responses."""
    broker = MagicMock()
    broker.connect.return_value = True
    broker.account_info.return_value = {
        "balance": 300.0, "equity": 300.0,
        "margin": 0.0, "free_margin": 300.0
    }
    broker.positions_get.return_value = []
    broker.order_send.return_value = {"ticket": 12345, "retcode": 10009}
    return broker

@pytest.fixture
def mock_market():
    """MockMarketAdapter returning configurable candle data."""
    market = MagicMock()
    return market

@pytest.fixture
def sample_candles():
    """Generate 200 M5 XAUUSD candles with realistic OHLCV."""
    base_price = 2350.0
    timestamps = [datetime(2026, 8, 6, 8, 0) + timedelta(minutes=5*i)
                  for i in range(200)]
    np.random.seed(42)
    closes = base_price + np.cumsum(np.random.randn(200) * 0.5)
    return [
        {
            "time": ts, "open": c - np.random.uniform(0, 2),
            "high": c + np.random.uniform(0, 5),
            "low": c - np.random.uniform(0, 5),
            "close": c, "volume": np.random.randint(100, 5000)
        }
        for ts, c in zip(timestamps, closes)
    ]

@pytest.fixture
def sample_features():
    """Pre-computed feature dict for detector tests."""
    return {
        "atr_14": 8.5, "rsi_14": 62.3, "ema_20": 2348.5,
        "ema_50": 2345.0, "vwap": 2349.2, "volume_ma": 1500,
        "spread": 2.5, "session": "london",
    }

@pytest.fixture
def mock_account():
    """Account state factory."""
    def _make(balance=300.0, equity=None, positions=None):
        return {
            "balance": balance,
            "equity": equity or balance,
            "positions": positions or [],
            "day_start_balance": balance,
        }
    return _make
```

### Mock Candle Patterns for Detectors

| Pattern | Detector | Candle Shape |
|---------|----------|-------------|
| Fair Value Gap (bullish) | `fvg_detector` | Gap between candle 1 high and candle 3 low |
| Fair Value Gap (bearish) | `fvg_detector` | Gap between candle 1 low and candle 3 high |
| Order Block (bullish) | `ob_detector` | Last down candle before strong up move |
| Break of Structure | `bos_detector` | Higher high / lower low beyond swing point |
| Liquidity Sweep | `liquidity_detector` | Wick beyond key level, close back inside |
| Imbalance (CVD) | `imbalance_detector` | Volume spike with directional close |
| Momentum Divergence | `momentum_detector` | Price HH + RSI LH (or inverse) |
| Velocity Spike | `velocity_detector` | Price change rate > 2σ in window |
| Recovery Pattern | `recovery_detector` | V-shaped reversal with volume confirmation |

```python
# tests/fixtures/candles.py
def make_fvg_bullish(base_price=2350.0):
    """3-candle pattern: gap between C1.high and C3.low."""
    return [
        {"open": base_price, "high": base_price + 3,
         "low": base_price - 2, "close": base_price - 1},
        {"open": base_price - 1, "high": base_price + 8,
         "low": base_price - 1, "close": base_price + 7},
        {"open": base_price + 7, "high": base_price + 10,
         "low": base_price + 5, "close": base_price + 9},
        # Gap: C1.high (2353) to C3.low (2355) = 2pt bullish FVG
    ]
```

### Coverage Targets

| Module | Target | Rationale |
|--------|--------|-----------|
| `core/features/` | ≥ 90% | Math correctness critical |
| `core/detectors/` | ≥ 85% | Signal quality drives PnL |
| `core/risk/` | ≥ 95% | Capital protection |
| `core/trailing/` | ≥ 90% | Exit quality drives PnL |
| `core/engine/` | ≥ 80% | Integration complexity |
| `adapters/` | ≥ 80% | Mock + gateway |
| `strategies/` | ≥ 75% | Strategy logic, some heuristics |
| `dashboard/` | ≥ 60% | UI layer, lower risk |
| **Overall** | **≥ 80%** | — |

### Regression Testing

```python
# tests/regression/test_v4_parity.py
def test_v4_parity_bystra_decision():
    """Same candle data + account state → same trade decision as V4."""
    # Load recorded V4 decision from fixtures
    v4_decision = load_fixture("v4_decisions/bystra_fvg_entry.json")
    
    # Run through portable engine with same inputs
    engine = build_engine(config=v4_decision["config"])
    result = engine.evaluate(v4_decision["candles"], v4_decision["account"])
    
    assert result.action == v4_decision["expected"]["action"]
    assert result.lot == pytest.approx(v4_decision["expected"]["lot"], abs=0.01)
    assert result.sl == pytest.approx(v4_decision["expected"]["sl"], abs=0.5)
```

---

## 24. Rollback Procedures

### Phase 1–3: No Production Impact

These phases run in parallel development branch. No production system affected.

```bash
# Rollback: simply revert commits on feature branch
cd /home/ubuntu/trading-intelligence-engine
git log --oneline --since="2026-08-06" --author="riri" | head -20
git revert <commit_range>

# Verification
git status
python -m pytest tests/unit/ tests/adapter/
```

### Phase 4: Engine Core

Engine runs as systemd service. Rollback switches back to old service.

```bash
# 1. Stop new portable engine
sudo systemctl stop tie-portable
sudo systemctl disable tie-portable

# 2. Re-enable old production engine
sudo systemctl enable tie-production
sudo systemctl start tie-production

# 3. Verify old engine running
sudo systemctl status tie-production
ps aux | grep -E "tie_|mt5_engine" | grep -v grep

# 4. Check no stuck positions
# (manual check on MT5 terminal or via gateway API)
curl -s http://localhost:18808/positions | jq .

# 5. Verify heartbeat
tail -20 /var/log/tie-production.log | grep -i heartbeat
```

### Phase 5: Dashboard

Dashboard is optional overlay. Engine unaffected by rollback.

```bash
# 1. Stop dashboard
sudo systemctl stop tie-dashboard 2>/dev/null
# or if running standalone:
pkill -f "tie-dashboard\|uvicorn.*dashboard"

# 2. Verify engine still running independently
sudo systemctl status tie-portable  # or tie-production

# 3. Optional: remove dashboard package
pip uninstall tie-dashboard 2>/dev/null
```

### Phase 6: Integration

Roll back to Phase 4 engine-only state (dashboard optional).

```bash
# 1. Stop all portable services
sudo systemctl stop tie-portable tie-dashboard

# 2. Revert to Phase 4 git state
cd /home/ubuntu/trading-intelligence-engine
git log --oneline | grep -i "phase.4\|4\.\|engine.core" | head -5
git checkout <phase4_tag>

# 3. Restart engine from Phase 4 state
sudo systemctl start tie-portable

# 4. Verify Phase 4 behavior
python -m pytest tests/integration/ -k "engine_loop"
tail -f logs/tie-engine.log | grep -i "scan\|decision\|heartbeat"
```

### Phase 7: Full Rollback

Complete revert to pre-portable production state.

```bash
# 1. STOP new portable engine (confirm no open positions first!)
curl -s http://localhost:18808/positions | jq '.count'
# If count > 0: MANUALLY CLOSE POSITIONS ON MT5 TERMINAL FIRST

sudo systemctl stop tie-portable tie-dashboard
sudo systemctl disable tie-portable tie-dashboard

# 2. START old production engine
sudo systemctl enable tie-production
sudo systemctl start tie-production

# 3. VERIFY old engine alive
sudo systemctl status tie-production
sleep 30
tail -30 /var/log/tie-production.log | grep -iE "started|heartbeat|scan"

# 4. VERIFY gateway connectivity
curl -s http://localhost:18808/health

# 5. VERIFY state consistency
# Check data/ directory for any portable-specific state files
ls -la data/*.json data/*.db 2>/dev/null
# Old engine should ignore portable state files

# 6. MONITOR for 1h
watch -n 60 'sudo systemctl status tie-production --no-pager | head -5; \
             tail -5 /var/log/tie-production.log'

# 7. NOTIFY stakeholders
echo "Rollback complete. Old production engine restored. $(date)" >> logs/rollback.log
```

### Rollback Decision Tree

```
Position open on portable engine?
├── YES → Close on MT5 terminal first → then rollback
└── NO → Proceed with rollback
         │
         Portable engine responsive?
         ├── YES → systemctl stop tie-portable (clean)
         └── NO  → kill -9 $(pgrep -f tie-portable) (force)
                   │
                   Any data in /tmp/tie_*?
                   ├── YES → cp /tmp/tie_* data/ (preserve state)
                   └── NO  → Continue
```

---

## 25. Performance Baseline

### Metrics to Capture from Current V4 Production

| Metric | How to Measure | Target | Baseline (V4) |
|--------|---------------|--------|---------------|
| Scan cycle latency | `@timeit` decorator on `_scan_symbol()` | < 200ms | _measure_ |
| Memory (RSS 24h) | `psutil.Process().memory_info().rss` logged hourly | < 150MB | _measure_ |
| Startup time | `time.time()` from import to first heartbeat log | < 5s | _measure_ |
| CPU usage (1h avg) | `psutil.cpu_percent(interval=3600)` | < 5% | _measure_ |
| Gateway API latency | `time.time()` around gateway HTTP calls (p50/p95/p99) | p95 < 100ms | _measure_ |
| Decision throughput | decisions logged per minute during active session | > 10/min | _measure_ |

### Measurement Implementation

```python
# core/metrics.py — lightweight instrumentation, no external deps

import time
import functools
import psutil
import logging

logger = logging.getLogger("tie.metrics")

def timeit(func):
    """Decorator: logs execution time of scan functions."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.debug(f"{func.__name__} took {elapsed_ms:.1f}ms")
        return result
    return wrapper

def measure_memory_mb() -> float:
    """Current process RSS in MB."""
    return psutil.Process().memory_info().rss / (1024 * 1024)

def measure_startup_time(start_ts: float) -> float:
    """Seconds since process start."""
    return time.time() - start_ts

def measure_cpu_pct(duration_seconds: int = 60) -> float:
    """Average CPU % over duration."""
    return psutil.cpu_percent(interval=duration_seconds)
```

### Baseline Capture Script

```bash
# scripts/capture_baseline.sh — run against live V4 production

#!/bin/bash
set -euo pipefail
OUT="baseline_$(date +%Y%m%d_%H%M%S).json"

echo "Capturing V4 production baseline..."

# 1. Scan cycle: grep from debug logs
SCAN_AVG=$(grep "scan_symbol.*took" logs/tie-engine.log | \
           tail -100 | awk -F'took ' '{print $2}' | \
           awk -F'ms' '{sum+=$1; n++} END {printf "%.1f", sum/n}')

# 2. Memory: snapshot
RSS_MB=$(ps -o rss= -p $(pgrep -f "tie_engine\|mt5_engine") | \
         awk '{printf "%.1f", $1/1024}')

# 3. Startup: from log timestamps
STARTUP=$(grep -m1 "heartbeat\|started\|ready" logs/tie-engine.log | \
          head -1)

# 4. CPU: 60s sample
CPU_PCT=$(top -b -n 60 -p $(pgrep -f "tie_engine\|mt5_engine") | \
          tail -1 | awk '{print $9}')

# 5. Gateway latency: from debug logs or curl timing
GATEWAY_P95=$(grep "gateway.*latency\|api.*took" logs/tie-engine.log | \
              tail -100 | awk -F'took ' '{print $2}' | \
              sort -n | awk 'NR==int(NR*0.95){print $1}')

# 6. Decision throughput
DPM=$(grep -c "decision\|trade_plan\|signal" logs/tie-engine.log | \
      awk -v lines=$(wc -l < logs/tie-engine.log) '{printf "%.1f", $1/(lines/12)}')

cat > "$OUT" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "scan_cycle_avg_ms": ${SCAN_AVG:-null},
  "memory_rss_mb": ${RSS_MB:-null},
  "startup_log_line": "${STARTUP:-null}",
  "cpu_pct_1h": ${CPU_PCT:-null},
  "gateway_latency_p95_ms": ${GATEWAY_P95:-null},
  "decisions_per_minute": ${DPM:-null}
}
EOF

echo "Baseline saved to $OUT"
```

### Performance Comparison Template

After portable engine runs for 24h, compare:

```bash
# Run same capture against portable engine
# Then diff:

python3 -c "
import json
v4 = json.load(open('baseline_v4.json'))
portable = json.load(open('baseline_portable.json'))
for k in v4:
    if k == 'timestamp': continue
    v4v = v4[k]
    ppv = portable[k]
    if v4v and ppv:
        diff = ((ppv - v4v) / v4v) * 100
        status = '✅' if abs(diff) < 20 else '⚠️'
        print(f'{status} {k}: V4={v4v} → Portable={ppv} ({diff:+.1f}%)')
"
```

### Profiling Hot Paths

```bash
# cProfile for scan cycle bottlenecks
python3 -m cProfile -s cumtime -m tie_engine run --once 2>&1 | head -30

# memory_profiler for leak detection
pip install memory_profiler
python3 -m memory_profiler tie_engine/run.py 2>&1 | grep "MiB"
```

---

*Document created by Riri. Version 3.0.0 — expanded with sprint dependency graph, effort estimates, config validation schema, testing strategy, rollback procedures, and performance baseline. Pending Boskuh review and approval before implementation begins.*
