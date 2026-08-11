# TIE V4 Portable — DETAILED Design Addendum
**Version:** 1.0.0  
**Date:** 2026-08-06  
**Author:** Riri (Trading Intelligence Engine)  
**Status:** Draft — Pending Boskuh Review  
**Purpose:** Expand architecture, workflow pipeline, and sprint task breakdowns beyond what the main doc covers.

> File ini ADDENDUM ke `tie-v4-portable-product-design.md`. Merge ke original setelah review.

---

## A. Architecture Deep Dive

### A.1 Data Flow Sequence — Step-by-Step

Setiap scan cycle, data mengalir lewat 10 transformasi. Di sini Riri detailkan apa yang terjadi di setiap step, tipe data masuk/keluar, dan edge case-nya.

```
STEP 1: FETCH
  Input:  symbol="XAUUSD", timeframes=["M1","M5","M15","H1","H4"], count=250
  Actor:  MarketDataAdapter.get_candles() + get_price()
  Output: Dict[str, List[Candle]]  ← {tf: [Candle(timestamp,o,h,l,c,vol,tf), ...]}
         PriceQuote(symbol, bid, ask, spread, timestamp)
  Edge:   - Gateway timeout → retry 3x (1s,2s,4s) → AdapterError → skip symbol
          - Empty candle list → log WARNING, skip symbol
          - Spread > 50 points → data still fetched (filter happens in Risk Gate)
  Time:   ~50-200ms (5 HTTP calls to gateway)

STEP 2: FEATURES
  Input:  Dict[str, List[Candle]]  (dari Step 1)
  Actor:  FeatureEngine.compute(candles)
  Output: FeatureSnapshot(
            atr={"M5": 5.2, "H1": 12.8, "H4": 28.3},  ← Dict, BUKAN float!
            volume_ratio={"M5": 1.3, "H1": 0.9},
            session="LONDON",
            regime_hint="TRENDING"
          )
  Edge:   - < 50 candles → ATR unreliable, use fallback period
          - All zeros → return safe defaults, log WARNING
  Note:   NO current_price field (bug #14 prevention)
  Time:   ~5-15ms (pure math, no IO)

STEP 3: REGIME
  Input:  FeatureSnapshot (dari Step 2)
  Actor:  RegimeEngine.detect(features)
  Output: RegimeSnapshot(
            regime=Regime.TRENDING,
            confidence=0.82,
            reason="ADX>25, EMA20>EMA50, higher highs"
          )
  Edge:   - Low confidence (<0.4) → regime=CHOPPY → OpportunityEngine may block
  Time:   ~1-3ms

STEP 4: CONTEXT
  Input:  price=PriceQuote, candles=Dict, session=FeatureSnapshot.session
  Actor:  ContextEngine.build(price, candles, session)
  Output: ScanContext(
            current_price=2352.45,
            session="LONDON",
            symbol="XAUUSD",
            sr_levels={"support": [2345.0, 2338.5], "resistance": [2360.0, 2372.0]},
            metadata={...}
          )
  Edge:   - No SR levels found → sr_levels={"support":[], "resistance":[]}
  Time:   ~3-8ms

STEP 5: OPPORTUNITY
  Input:  features=FeatureSnapshot, regime=RegimeSnapshot, symbol="XAUUSD"
  Actor:  OpportunityEngine.evaluate(features, regime, symbol)
  Output: OpportunitySnapshot(
            open=True,
            score=88.0,
            reason="",
            session_score=95.0
          )
  Edge:   - ASIA session XAUUSD → score=25 → open=False → STOP HERE
          - Spread too high → open=False, reason="spread_exceeded"
          - ATR out of range → open=False, reason="atr_too_low"
  Time:   ~1-2ms

STEP 6: STRATEGIES
  Input:  context=ScanContext, features=FeatureSnapshot
  Actor:  StrategyManager.run_all(context, features)
  Output: List[StrategyResult]  ← 0-3 results
          Example: [
            StrategyResult(strategy_code="B", score=72.0, signal=Signal(direction="buy", ...)),
            StrategyResult(strategy_code="S", score=65.0, signal=Signal(direction="buy", ...))
          ]
  Edge:   - No strategy fires → empty list → STOP HERE
          - Strategy crashes → catch per-strategy, log ERROR, continue to next
          - Score < MIN_ENTRY_SCORE → filtered out
  Time:   ~20-80ms (14 detectors for Bystra, multiple engines for Aggressive/SemiHFT)

STEP 7: FUSION
  Input:  List[StrategyResult] (dari Step 6)
  Actor:  MultiStrategyRuntime.fuse(results)
  Output: Fused TradePlan or None
          Example: TradePlan(
            symbol="XAUUSD",
            action="buy",
            entry_zone={"low": 2351.95, "high": 2352.95},
            stop_loss=2345.0,
            take_profit=2370.0,
            lot=0.01,
            score=68.5,
            strategy_code="BS"  ← Bystra + SemiHFT
          )
  Edge:   - Conflicting directions (BUY + SELL) → None → STOP HERE
          - Dedup: same direction within DEDUP_WINDOW (120s) → None
          - Low fused score → None
  Time:   ~1-3ms

STEP 8: TRADE PLAN
  Input:  fused=TradePlan, context=ScanContext, features=FeatureSnapshot
  Actor:  _build_trade_plan() + ExitOrchestrator.optimize()
  Output: TradePlan (refined SL/TP)
  Edge:   - Fix #12: direction param explicit, never inferred from SL/TP
          - Fix #46: SELL TP must be < entry
  Time:   ~2-5ms

STEP 9: RISK GATE
  Input:  plan=TradePlan, equity=float
  Actor:  RiskRegistry.evaluate(plan, risk_ctx)
  Output: RiskDecision(passed=True/False, reason="...", details={...})
  Rules:  1. SessionRule — allowed_sessions from config
          2. SpreadRule — max_points=50
          3. SL/TP Validation — fix #17 (entry<=0 guard), fix #46 (SELL TP direction)
          4. DynamicLot — _max_lot_for_equity(equity)
          5. DailyTarget — profit >= target → block
  Edge:   - Any rule throws exception → FAIL-safe (reject), log ERROR
  Time:   ~1-2ms

STEP 10: EXECUTE or OBSERVE
  Input:  decision=RiskDecision, plan=TradePlan
  Actor:  BrokerAdapter.submit_order() + GateObservatory.record()
  Output: OrderResponse(success=True, ticket="12345")
  If PASS: submit_order(OrderRequest(
            symbol="XAUUSD", direction="buy", volume=0.01,
            stop_loss=2345.0, take_profit=2370.0,
            comment="TIE_BS_BUY", magic=20260806
          ))
  If FAIL: observatory.record(decision, plan)  ← logged for postmortem
  Edge:   - Order rejected by broker → log ERROR, continue (don't crash)
          - Fix #29: volume key, not lot
          - Fix #34: lot from decision.metadata["volume"], never hardcoded
  Time:   ~50-200ms (HTTP to gateway) or ~1ms (observatory write)
```

**Total pipeline time per symbol:** ~130-320ms (dominated by gateway HTTP calls)

### A.2 Engine State Machine

```
                    ┌──────────────────────────────────────┐
                    │                                      │
                    ▼                                      │
              ┌──────────┐    weekend()                 ┌──┴───────┐
              │          │──────────────────────────────▶│          │
              │  NORMAL  │                               │ WEEKEND  │
              │  (scan)  │◀──────────────────────────────│ (sleep)  │
              │          │    Monday 00:00 UTC           │          │
              └────┬─────┘                               └──────────┘
                   │
                   │ target_hit()
                   ▼
              ┌──────────┐    hibernate_timeout    ┌──────────┐
              │          │───────────────────────▶│          │
              │ HIBERNATE│    (20min default)      │  NORMAL  │
              │ (sleep)  │                         │          │
              └──────────┘                         └──────────┘
                   │
                   │ halt file exists
                   ▼
              ┌──────────┐    rm data/halt         ┌──────────┐
              │          │───────────────────────▶│          │
              │  HALTED  │                         │  NORMAL  │
              │ (sleep)  │                         │          │
              └──────────┘                         └──────────┘

Transitions:
  NORMAL → WEEKEND:   weekday() in (5, 6) and no positions open
  NORMAL → HIBERNATE: equity - day_start >= daily_target
  NORMAL → HALTED:    os.path.exists("data/halt")
  WEEKEND → NORMAL:   weekday() < 5 (Monday 00:00 UTC)
  HIBERNATE → NORMAL: sleep timer expires (hibernate_interval seconds)
  HALTED → NORMAL:    halt file removed (manual: rm data/halt)

Sleep durations:
  NORMAL scan:     engine.scan_interval (default 10s)
  HIBERNATE:       engine.hibernate_interval (default 1200s = 20min)
  WEEKEND:         300s (5min) — re-check if weekend ended early
  HALTED:          60s — re-check if halt file removed
```

### A.3 Error Recovery Matrix

| Layer | Error | Recovery | Max Retry | Backoff | Crash? |
|-------|-------|----------|-----------|---------|--------|
| **Gateway HTTP** | Connection timeout | Retry 3x | 3 | 1s, 2s, 4s | No → skip symbol |
| **Gateway HTTP** | 422 Unprocessable | No retry | 0 | — | No → log + skip |
| **Gateway HTTP** | 500 Server Error | Retry 3x | 3 | 2s, 4s, 8s | No → skip symbol |
| **Feature Engine** | Empty candles | Safe defaults | 0 | — | No → WARNING log |
| **Feature Engine** | NaN in ATR | Fallback period | 1 | — | No → WARNING log |
| **Regime Engine** | Low confidence | Default CHOPPY | 0 | — | No → opportunity may block |
| **Strategy** | Detector crash | Catch per-strategy | 0 | — | No → next strategy |
| **Risk Gate** | Rule exception | FAIL-safe (reject) | 0 | — | No → log ERROR |
| **Order Submit** | Broker reject | Log + continue | 0 | — | No → next cycle |
| **Order Modify** | Full-replace fail | Log + retry next cycle | 1 | 10s | No |
| **Position Monitor** | Position disappears | Log WARNING | 0 | — | No |
| **Main Loop** | Uncaught exception | Log CRITICAL, sleep 30s | ∞ | 30s | NEVER |

**Principle: Engine NEVER crashes.** Worst case: sleeps and retries.

### A.4 Component Interaction Matrix

```
                DataFeed  Feature  Regime  Context  OppEngine  Strategy  RiskGate  Executor  PosMon  Trail  Observer
DataFeed          —         →        —       —        —          —         —         —         —      —       —
Feature           ←         —        →       —        —          —         —         —         —      —       —
Regime            —         ←        —       —        →          —         —         —         —      —       —
Context           →         —        —        —       —          →         —         —         —      —       —
OppEngine         —         →        →       —        —          —         —         —         —      —       —
Strategy          —         →        —       →        —          —         →         —         —      —       —
RiskGate          —         —        —       —        —          ←         —         →         —      —       →
Executor          →         —        —       —        —          —         —         —         —      →       —
PosMon            →         —        —       —        —          —         —         ←         —      →       →
Trailing          →         —        —       —        —          —         —         ←         ←      —       →
Observer          —         —        —       —        —          —         ←         ←         ←      ←       —
```

`→` = sends data to, `←` = receives data from

---

## B. Pipeline Walkthrough — Contoh Real

### B.1 Scenario: XAUUSD BUY Signal (Full Pipeline — PASS)

```
Waktu: 2026-08-06 14:30:15 UTC (London session)
Symbol: XAUUSD
Equity: $350.00
Day-start: $350.00 (PnL = $0.00)

STEP 1 — FETCH:
  candles = {
    "M1": [Candle(14:25, o=2351.2, h=2352.8, l=2350.5, c=2352.1, vol=1250), ...],  # 250 candles
    "M5": [Candle(14:00, o=2348.5, h=2353.2, l=2347.8, c=2352.0, vol=5800), ...],
    "M15": [...],
    "H1": [Candle(13:00, o=2345.0, h=2354.0, l=2344.2, c=2352.5, vol=18500), ...],
    "H4": [Candle(12:00, o=2340.0, h=2355.0, l=2338.0, c=2352.0, vol=42000), ...]
  }
  price = PriceQuote(bid=2352.30, ask=2352.55, spread=2.5, ts=1691329815)
  gateway_latency = 120ms

STEP 2 — FEATURES:
  features = FeatureSnapshot(
    atr={"M1": 1.8, "M5": 5.2, "M15": 8.5, "H1": 12.8, "H4": 28.3},
    volume_ratio={"M5": 1.4, "H1": 1.1},  ← above average
    session="LONDON",
    regime_hint="TRENDING"
  )

STEP 3 — REGIME:
  regime = RegimeSnapshot(
    regime=Regime.TRENDING,
    confidence=0.85,
    reason="ADX=32 (>25), EMA20=2349.5 > EMA50=2344.0, consecutive higher highs on H1"
  )

STEP 4 — CONTEXT:
  context = ScanContext(
    current_price=2352.42,
    session="LONDON",
    symbol="XAUUSD",
    sr_levels={
      "support": [2345.0, 2338.5, 2330.0],
      "resistance": [2360.0, 2372.0, 2385.0]
    },
    metadata={"h1_trend": "bullish", "m5_momentum": "strong"}
  )

STEP 5 — OPPORTUNITY:
  opp = OpportunitySnapshot(
    open=True,          ← London session, spread OK, ATR in range
    score=92.0,
    reason="",
    session_score=95.0  ← London = 95
  )

STEP 6 — STRATEGIES:
  Bystra: StrategyResult(
    strategy_code="B", score=72.0,
    signal=Signal(direction="buy", entry_zone={"low": 2351.92, "high": 2352.92},
                  stop_loss=2345.0, take_profit=2370.0, confidence=0.72)
    ← triggered by: SNRC1 (support bounce at 2345.0) + Mother Candle breakout
  )
  Aggressive: StrategyResult(strategy_code="A", score=0.0, signal=None)
    ← no trigger: momentum burst not detected
  SemiHFT: StrategyResult(
    strategy_code="S", score=68.0,
    signal=Signal(direction="buy", entry_zone={"low": 2352.0, "high": 2352.8},
                  stop_loss=2348.0, take_profit=2360.0, confidence=0.68)
    ← triggered by: tick velocity spike + micro momentum
  )

STEP 7 — FUSION:
  fused = TradePlan(
    symbol="XAUUSD", action="buy",
    entry_zone={"low": 2351.95, "high": 2352.95},  ← averaged from B+S
    stop_loss=2345.0,  ← wider SL from Bystra (swing)
    take_profit=2368.0, ← between Bystra TP (2370) and SemiHFT TP (2360)
    lot=0.01,
    score=70.0,  ← weighted: B(72*1.0) + S(68*1.0) / 2
    strategy_code="BS"
  )

STEP 8 — TRADE PLAN:
  ExitOrchestrator.optimize(fused, direction="buy")
    → TP adjusted: 2368.0 (no change, already > entry)
    → SL verified: 2345.0 < entry (correct for BUY)

STEP 9 — RISK GATE:
  risk_ctx = RiskContext(entry=2352.42, sl=2345.0, tp=2368.0, lot=0.01, equity=350.0,
                         session="LONDON", symbol="XAUUSD", strategy_code="BS")
  
  Rule 1 — SessionRule: "LONDON" in allowed_sessions → PASS ✅
  Rule 2 — SpreadRule: spread=2.5 < max_points=50 → PASS ✅
  Rule 3 — SL/TP Validation:
    - SL < entry (2345.0 < 2352.42) → PASS ✅
    - TP > entry (2368.0 > 2352.42) → PASS ✅
    - Risk:Reward = 1:2.17 → PASS ✅
  Rule 4 — DynamicLot: equity=$350 < $2000 → flat_lot=0.01 → PASS ✅
  Rule 5 — DailyTarget: PnL=$0.00 < target=$30.00 → PASS ✅
  
  decision = RiskDecision(passed=True, reason="all rules passed")

STEP 10 — EXECUTE:
  broker.submit_order(OrderRequest(
    symbol="XAUUSD", direction="buy", volume=0.01,
    stop_loss=2345.0, take_profit=2368.0,
    comment="TIE_BS_BUY", magic=20260806
  ))
  → OrderResponse(success=True, ticket="54321")
  
  observatory.record(decision, plan)
  → SQLite: gate_decisions INSERT (passed=1)
```

### B.2 Scenario: XAUUSD Rejected by Risk Gate (FAIL)

```
Waktu: 2026-08-06 02:15:00 UTC (Asia session)
Symbol: XAUUSD
Equity: $342.00
Day-start: $350.00 (PnL = -$8.00)

... Steps 1-7 same pattern, Bystra fires BUY signal ...

STEP 9 — RISK GATE:
  risk_ctx = RiskContext(entry=2348.5, sl=2342.0, tp=2360.0, lot=0.01, equity=342.0,
                         session="ASIA", symbol="XAUUSD", strategy_code="B")
  
  Rule 1 — SessionRule: "ASIA" in allowed_sessions → PASS ✅
    (allowed: ["LONDON", "NEW_YORK", "OVERLAP", "ASIA"])
  Rule 2 — SpreadRule: spread=45.0 < max_points=50 → PASS ✅ (barely)
  Rule 3 — SL/TP Validation: all OK → PASS ✅
  Rule 4 — DynamicLot: equity=$342 < $2000 → flat_lot=0.01 → PASS ✅
  Rule 5 — DailyTarget: PnL=-$8.00 < target=$30.00 → PASS ✅
  
  BUT: OpportunityEngine already blocked (score=25 for ASIA session)
  → Pipeline stopped at Step 5. Never reached Risk Gate.
  
  observatory.record(decision, plan)  ← not recorded (stopped before gate)
```

### B.3 Data Transformation Summary

```
Raw Candles (250×5 TF = 1250 Candle objects)
    ↓ FeatureEngine.compute()
FeatureSnapshot (atr dict, volume_ratio dict, session, regime_hint)
    ↓ RegimeEngine.detect()
RegimeSnapshot (enum, confidence float, reason string)
    ↓ ContextEngine.build()
ScanContext (price, session, symbol, SR levels dict)
    ↓ OpportunityEngine.evaluate()
OpportunitySnapshot (bool, score float, reason string)
    ↓ StrategyManager.run_all()
List[StrategyResult] (0-3 items, each with optional Signal)
    ↓ MultiStrategyRuntime.fuse()
TradePlan (symbol, action, entry_zone, SL, TP, lot, score, strategy_code)
    ↓ ExitOrchestrator.optimize()
TradePlan (refined SL/TP)
    ↓ RiskRegistry.evaluate()
RiskDecision (bool, reason, details)
    ↓ BrokerAdapter.submit_order()
OrderResponse (bool, ticket or error)
```

---

## C. Detailed Sprint Task Breakdowns

### PHASE 1: Foundation (Week 1-2)

#### Sprint 1.1 — Package Skeleton + Config (Day 1-3)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Create tie_v4/ folder + all subdirs | 0.5 | Directory tree | `find tie_v4/ -type d` |
| 2 | Write all __init__.py files | 0.5 | __init__.py with version string | `python -c "import tie_v4; print(tie_v4.__version__)"` |
| 3 | Write pyproject.toml — metadata, deps, entry point | 1.0 | pyproject.toml | `pip install -e .` |
| 4 | Write config.py — ConfigLoader class | 2.0 | config.py | `python -c "from tie_v4.config import ConfigLoader"` |
| 5 | Write config/engine.yaml — full default config | 1.0 | engine.yaml | YAML parses without error |
| 6 | Write __main__.py — argparse + config load + print | 1.5 | __main__.py | `python -m tie_v4 --config config/engine.yaml` |
| 7 | Write Makefile — install, run, test targets | 0.5 | Makefile | `make install` |
| 8 | Write requirements.txt — pyyaml, requests | 0.25 | requirements.txt | `pip install -r requirements.txt` |
| 9 | Write tests/test_config.py | 1.5 | test file | `pytest tests/test_config.py -v` |
| 10 | Run acceptance checks (all 5 criteria) | 0.5 | green | All acceptance criteria pass |
| **TOTAL** | | **9.25h** | | |

**Key Signatures:**
```python
class ConfigLoader:
    @staticmethod
    def load(path: str, cli_overrides: dict = None) -> dict
    @staticmethod
    def _deep_merge(base: dict, override: dict) -> None
```

**Tests:** test_load_yaml, test_env_var_expansion, test_missing_var_keeps_placeholder, test_default_values, test_cli_override, test_deep_merge, test_missing_file_raises

**Rollback:** Delete tie_v4/ directory. Zero external impact.

---

#### Sprint 1.2 — Adapter Base + Mock (Day 4-6)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Write adapters/base.py — BrokerAdapter + MarketDataAdapter ABC | 2.0 | base.py | `from tie_v4.adapters.base import BrokerAdapter` |
| 2 | Write adapters/models.py — all data models (Candle, PriceQuote, AccountInfo, Position, OrderRequest, OrderResponse) | 2.0 | models.py | `from tie_v4.adapters.models import Candle` |
| 3 | Write adapters/mt5_mock.py — full mock implementation | 3.0 | mt5_mock.py | Mock submit_order → ticket returned |
| 4 | Write adapters/registry.py — create_broker() + create_market() | 1.5 | registry.py | `create_broker({"broker":"mock"})` returns MT5MockBroker |
| 5 | Write tests/test_mock_broker.py | 1.5 | test file | `pytest tests/test_mock_broker.py -v` |
| 6 | Write tests/test_mock_market.py | 1.0 | test file | `pytest tests/test_mock_market.py -v` |
| 7 | Write requirements-dev.txt | 0.25 | requirements-dev.txt | `pip install -r requirements-dev.txt` |
| **TOTAL** | | **11.25h** | | |

**Tests:**
- test_mock_broker.py: submit_order_returns_ticket, modify_sends_both_sl_and_tp, close_position_removes_from_list, get_positions_returns_all, get_account_returns_balance
- test_mock_market.py: get_candles_returns_count, get_price_returns_bid_ask_spread
- test_registry.py: auto_detect_mock, explicit_mode_selection, auto_fallback

**Rollback:** Delete adapters/ directory.

---

#### Sprint 1.3 — MT5 Gateway Adapter (Day 7-9)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Write adapters/mt5_gateway.py — MT5GatewayBroker class | 3.0 | mt5_gateway.py | `MT5GatewayBroker(url, token).get_account()` |
| 2 | Implement submit_order with retry logic (3x exponential backoff) | 1.5 | submit_order | Simulated timeout → retry → success |
| 3 | Implement modify_order (full-replace: sl AND tp) | 1.0 | modify_order | Test: tp=None → read current from get_positions() |
| 4 | Implement get_positions, get_candles, get_price | 2.0 | remaining methods | All return correct types |
| 5 | SSL: verify=False for Cloudflare tunnel | 0.25 | SSL config | Works with tunnel URL |
| 6 | Write tests/test_gateway_adapter.py (mock HTTP) | 2.0 | test file | `pytest tests/test_gateway_adapter.py -v` |
| 7 | Write tests/test_gateway_integration.py (manual) | 0.5 | test file | Manual: `python -c "from tie_v4.adapters..."` |
| **TOTAL** | | **10.25h** | | |

**Key Signatures:**
```python
class MT5GatewayBroker(BrokerAdapter):
    def __init__(self, url: str, token: str, timeout: int = 10)
    def _request(self, method: str, path: str, **kwargs) -> dict  # retry wrapper
```

**Acceptance:**
- get_account() returns real account data from production gateway
- modify_order() always sends both sl AND tp
- Timeout → retry 3x → AdapterError with clear message
- Works with Cloudflare tunnel URL

**Rollback:** Delete mt5_gateway.py.

---

#### Sprint 1.4 — MT5 Native Adapter + Docker (Day 10-14)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Write adapters/mt5_native.py — MT5NativeBroker class | 3.0 | mt5_native.py | On Windows: get_account() returns real data |
| 2 | Implement all methods (submit, modify, close, positions, candles, price) | 3.0 | all methods | Mock MetaTrader5 module tests pass |
| 3 | Write requirements-win.txt | 0.25 | requirements-win.txt | MetaTrader5>=5.0.45 |
| 4 | Update registry.py: auto-detect platform | 1.0 | registry.py | Windows+MT5→native, Linux→gateway |
| 5 | Write Dockerfile | 1.0 | Dockerfile | `docker build .` succeeds |
| 6 | Write tests/test_native_adapter.py | 1.0 | test file | `pytest tests/test_native_adapter.py -v` |
| 7 | Write tests/test_registry_platform.py | 0.5 | test file | Platform detection tests |
| **TOTAL** | | **9.75h** | | |

**Rollback:** Delete mt5_native.py, Dockerfile.

---

### PHASE 2: Core Extraction (Week 3-4)

#### Sprint 2.1 — Features + Models (Day 15-17)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Extract FeatureSnapshot dataclass to core/features/models.py | 1.0 | models.py | `from tie_v4.core.features.models import FeatureSnapshot` |
| 2 | Extract FeatureEngine.compute() to core/features/engine.py | 3.0 | engine.py | `FeatureEngine().compute(mock_candles)` returns snapshot |
| 3 | Fix: atr is Dict[str, float], NOT float | 1.0 | fix | `snapshot.atr.get('M5', 0.0)` works |
| 4 | Fix: NO current_price on FeatureSnapshot (bug #14) | 0.5 | fix | `hasattr(snapshot, 'current_price')` is False |
| 5 | Write comprehensive tests for edge cases | 2.5 | test file | Empty candles, single candle, all zeros, realistic data |
| 6 | Verify pure Python (no external deps beyond stdlib+numpy) | 0.5 | verified | `grep -r "import" core/features/ | grep -v stdlib numpy` |
| **TOTAL** | | **8.5h** | | |

**Tests:**
- test_compute_returns_snapshot — basic happy path
- test_atr_is_dict — atr is Dict[str, float], not float
- test_no_current_price — FeatureSnapshot has no current_price field
- test_empty_candles — returns safe defaults
- test_single_candle — minimal data works
- test_all_zeros — no crash on zero values

**Rollback:** Delete core/features/.

---

#### Sprint 2.2 — Regime + Opportunity (Day 18-20)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Extract RegimeEngine.detect() to core/regime/engine.py | 2.0 | engine.py | TRENDING/RANGING/CHOPPY detection works |
| 2 | Extract Regime enum + RegimeSnapshot to core/regime/models.py | 0.5 | models.py | `Regime.TRENDING.value == "trending"` |
| 3 | Extract OpportunityEngine.evaluate() to core/opportunity/engine.py | 2.5 | engine.py | Session scoring works |
| 4 | Extract OpportunitySnapshot + BlockReason to core/opportunity/models.py | 0.5 | models.py | BlockReason enum |
| 5 | Session score logic: ASIA=25, LONDON=95, NEW_YORK=88, OVERLAP=98 | 1.0 | config-driven | Scores match config |
| 6 | Write test_regime.py | 1.5 | test file | Trending pattern → TRENDING, flat → RANGING |
| 7 | Write test_opportunity.py | 1.5 | test file | Asia XAUUSD → score 25, London → score 95 |
| **TOTAL** | | **9.5h** | | |

**Tests:**
- test_trending_detection — ADX>25 + higher highs → TRENDING
- test_ranging_detection — flat ADX + bounded range → RANGING
- test_asia_blocked — ASIA session XAUUSD → score 25 (blocked)
- test_london_open — LONDON session → score 95 (open)
- test_crypto_no_session_block — BTCUSD 24/7, no session block

**Rollback:** Delete core/regime/, core/opportunity/.

---

#### Sprint 2.3 — Context + Risk Rules (Day 21-23)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Extract ContextEngine.build() to core/context/engine.py | 2.0 | engine.py | SR levels extracted from candles |
| 2 | Extract ScanContext to core/context/scan_context.py | 0.5 | scan_context.py | Dataclass with all fields |
| 3 | Extract build_risk_registry() to core/rules/registry.py | 2.0 | registry.py | Configurable rule chain |
| 4 | Extract TPValidationRule to core/rules/sl_tp_validation.py | 1.5 | sl_tp_validation.py | Fix #17 + #46 |
| 5 | Extract SpreadRule to core/rules/spread_rule.py | 1.0 | spread_rule.py | Configurable max_points |
| 6 | Extract SessionRule to core/rules/session_rule.py | 1.0 | session_rule.py | "ASIA" not "ASIAN" (fix #13) |
| 7 | Extract _max_lot_for_equity() to core/rules/plugins/dynamic_lot.py | 1.0 | dynamic_lot.py | Tier boundaries correct |
| 8 | Write test_risk_registry.py | 2.0 | test file | Full gate chain tests |
| 9 | Write test_dynamic_lot.py | 1.0 | test file | All tier boundaries |
| 10 | Write test_context.py | 1.0 | test file | SR extraction, session derivation |
| **TOTAL** | | **13.0h** | | |

**Tests:**
- test_risk_registry_pass — all rules pass → RiskDecision(passed=True)
- test_risk_registry_session_fail — ASIA blocked → RiskDecision(passed=False)
- test_tp_validation_sell_above_entry — SELL TP > entry → REJECT (fix #46)
- test_tp_validation_entry_zero — entry <= 0 → APPROVE (skip, fix #17)
- test_lot_equity_300 → 0.01, test_lot_equity_500 → 0.01, test_lot_equity_2001 → 0.05
- test_session_rule_asia_not_asian — "ASIA" works, "ASIAN" rejected (fix #13)

**Rollback:** Delete core/context/, core/rules/.

---

#### Sprint 2.4 — Strategy Interfaces (Day 24-28)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Extract BaseStrategy ABC to core/strategy/base.py | 1.5 | base.py | ABC with analyze() method |
| 2 | Extract StrategyResult, TradePlan, Signal to core/strategy/result.py | 1.5 | result.py | All dataclasses |
| 3 | Extract ExitOrchestrator to core/strategy/exit_orchestrator.py | 2.0 | exit_orchestrator.py | Fix #12: explicit direction param |
| 4 | Extract StrategyManager to core/strategy/manager.py | 2.0 | manager.py | Config-driven enable/disable |
| 5 | Write test_exit_orchestrator.py | 2.0 | test file | BUY/SELL direction guard |
| 6 | Write test_strategy_manager.py | 1.5 | test file | Mock strategy, verify run_all |
| **TOTAL** | | **10.5h** | | |

**Tests:**
- test_exit_orchestrator_buy_widens_tp — BUY: TP adjusted correctly
- test_exit_orchestrator_sell_widens_tp — SELL: TP adjusted correctly
- test_exit_orchestrator_direction_guard — fix #12: never infer from SL/TP
- test_strategy_manager_run_all — all enabled strategies run
- test_strategy_manager_disable — `strategies.aggressive.enabled: false` → skipped

**Rollback:** Delete core/strategy/.

---

### PHASE 3: Strategy Migration (Week 5-6)

#### Sprint 3.1 — Bystra Migration (Day 29-31)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Create strategies/bystra/ package structure | 0.5 | dirs + __init__.py | Import works |
| 2 | Extract BystraStrategy(BaseStrategy) to strategy.py | 3.0 | strategy.py | analyze() returns StrategyResult |
| 3 | Migrate all 14 detectors to detectors/ | 4.0 | 14 detector files | All importable |
| 4 | Extract common.py — find_swing_pivots, find_nearest_sr | 1.5 | common.py | H1 swing pivots for SR |
| 5 | Write config.py — configurable thresholds | 1.0 | config.py | From YAML config |
| 6 | Write metadata.py — strategy_code="B", name="Bystra" | 0.5 | metadata.py | strategy_code="B" |
| 7 | Write tests/test_bystra.py | 2.0 | test file | Mock candle patterns → signals |
| 8 | Write tests/test_detectors.py | 2.5 | test file | Each detector with known pattern |
| **TOTAL** | | **15.0h** | | |

**Acceptance:**
- BystraStrategy.analyze(mock_context, mock_features) returns valid StrategyResult
- All 14 detectors importable and callable
- strategy_code="B" → order comment "TIE_B_BUY"
- H1 swing pivots used for SR (not M5)

**Rollback:** Delete strategies/bystra/, detectors/.

---

#### Sprint 3.2 — Aggressive Migration (Day 32-34)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Create strategies/aggressive/ package structure | 0.5 | dirs | Import works |
| 2 | Extract AggressiveStrategy(BaseStrategy) | 3.0 | strategy.py | Fix #14: context.current_price |
| 3 | Migrate sub-engines (momentum, velocity, microstructure, liquidity, vwap) | 3.0 | 5 engine files | All importable |
| 4 | Migrate regime engine + detectors (7 detectors) | 2.0 | regime + detectors | All work |
| 5 | Fix #15: entry_zone never {0,0} | 0.5 | fix | entry_zone has valid prices |
| 6 | Fix #18: weights = momentum:0.30, velocity:0.25, micro:0.20, trend:0.15, liquidity:0.05, vwap:0.05 | 0.5 | fix | Weights verified |
| 7 | Write tests/test_aggressive.py | 1.5 | test file | Price from context, entry_zone populated |
| **TOTAL** | | **11.0h** | | |

**Rollback:** Delete strategies/aggressive/.

---

#### Sprint 3.3 — SemiHFT Migration (Day 35-37)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Create strategies/semi_hft/ package structure | 0.5 | dirs | Import works |
| 2 | Extract SemiHFTStrategy(BaseStrategy) | 3.0 | strategy.py | Entry score ≥ 60 |
| 3 | Migrate entry_score.py — MIN_ENTRY_SCORE=60 from config | 1.0 | entry_score.py | Threshold matches config |
| 4 | Migrate fast_risk.py — _lot(equity), _swing_pivot() with fix #16 | 1.5 | fast_risk.py | _lot(300)=0.01, pivot guard |
| 5 | Migrate sub-engines (tick_velocity, volatility, recovery, etc.) | 3.0 | 8 engine files | All importable |
| 6 | Write tests/test_semi_hft.py | 1.5 | test file | Entry score threshold, lot sizing |
| 7 | Write tests/test_fast_risk.py | 1.0 | test file | Lot tiers, swing_pivot guard |
| **TOTAL** | | **11.5h** | | |

**Rollback:** Delete strategies/semi_hft/.

---

#### Sprint 3.4 — Strategy Integration Test (Day 38-42)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Extract MultiStrategyRuntime.fuse() to runtime/multi_strategy.py | 2.0 | multi_strategy.py | Weighted fusion works |
| 2 | Extract plan_to_decision() to runtime/tradeplan_adapter.py | 1.5 | tradeplan_adapter.py | Fix #46: direction guard |
| 3 | Strategy naming: TIE_B_BUY, TIE_BA_SELL, TIE_BAS_BUY | 1.0 | naming logic | All codes map correctly |
| 4 | Dedup logic: same direction within DEDUP_WINDOW → skip | 1.0 | dedup | Second signal within 120s rejected |
| 5 | Write test_multi_strategy.py | 2.0 | test file | Fusion, dedup, weighted scoring |
| 6 | Write test_strategy_integration.py | 3.0 | test file | Full pipeline: features → strategies → risk → decision |
| **TOTAL** | | **10.5h** | | |

**Tests:**
- test_fuse_bystra_aggressive → BA_ setup
- test_fuse_all_three → BAS_ setup
- test_dedup_within_window → rejected
- test_dedup_outside_window → accepted
- test_direction_guard_sell — SELL TP < entry enforced
- test_full_pipeline_mock_data — mock market → decision

**Rollback:** Delete runtime/multi_strategy.py, runtime/tradeplan_adapter.py.

---

### PHASE 4: Runtime (Week 7-8)

#### Sprint 4.1 — Engine Core Loop (Day 43-45)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Write runtime/engine.py — TIEEngine class | 5.0 | engine.py | Main loop runs |
| 2 | Implement run() — heartbeat, halt, hibernate, market check, scan, monitor, sleep | 3.0 | run() | One scan cycle completes |
| 3 | Implement _scan_symbol() — 10-step pipeline | 3.0 | _scan_symbol() | Pipeline produces decision |
| 4 | Lot injection: fast_risk._lot(equity) → decision.metadata["volume"] | 1.0 | lot injection | Fix #29 verified |
| 5 | risk_ctx.lot = decision.metadata.get("volume", 0.01) | 0.5 | fix | Fix #34: never hardcoded |
| 6 | Write tests/test_engine.py | 2.0 | test file | Halt, heartbeat, dry_run, hibernate |
| **TOTAL** | | **14.5h** | | |

**Acceptance:**
- TIEEngine(dry_run=True).run() — runs one scan cycle, no real trades
- Heartbeat written to data/heartbeat.txt
- `touch data/halt` → engine stops scanning
- Lot from strategy → risk_ctx matches (no hardcoded 0.02)

**Rollback:** Delete runtime/engine.py.

---

#### Sprint 4.2 — Trailing Consolidation (Day 46-48)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Consolidate TrailingManager + PositionMonitor + manual_trailing_v2 → single trailing_manager.py | 4.0 | trailing_manager.py | One trailing system |
| 2 | Extract ContractExecutor — BE lock, trailing, partial TP, early exit | 3.0 | contract_executor.py | All exit types work |
| 3 | Per-strategy exit configs (B/A/S profiles from YAML) | 1.0 | config-driven | S triggers BE at 0.15 ATR vs B at 0.5 |
| 4 | Fix #35: modify_order() always sends BOTH sl AND tp | 0.5 | fix | Never (sl, None) or (None, tp) |
| 5 | Write tests/test_trailing_manager.py | 2.0 | test file | BE lock, trail offset |
| 6 | Write tests/test_contract_executor.py | 1.5 | test file | Partial TP, early exit |
| **TOTAL** | | **12.0h** | | |

**Acceptance:**
- Only ONE process modifies positions: TrailingManager
- modify_order() always sends (sl, tp) pair
- Per-strategy trailing: S at 0.15 ATR, B at 0.5 ATR
- No external manual_trailing_v2.py needed

**Rollback:** Restore old trailing_manager.py + manual_trailing_v2.py.

---

#### Sprint 4.3 — Position Monitor + Trade Tracker (Day 49-51)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Write position_monitor.py — PositionMonitor(broker, trailing_manager) | 2.0 | position_monitor.py | Detects open/close |
| 2 | Write trade_tracker.py — TradeOutcomeTracker | 2.0 | trade_tracker.py | Win/loss to data/wins.json |
| 3 | Write governance/daily_governor.py — DailyProfitGovernorV2 | 2.0 | daily_governor.py | Target hit → hibernate |
| 4 | Write governance/trade_budget.py — TradeBudgetManager | 1.0 | trade_budget.py | Budget limits |
| 5 | Day-start dual-write: data/day_start.json + /tmp/tie_day_start.json | 1.0 | dual-write | Fix #41 verified |
| 6 | Weekend guard: no reset on Sat/Sun | 0.5 | fix | Fix #45 verified |
| 7 | Write tests (3 test files) | 2.5 | test files | All pass |
| **TOTAL** | | **11.0h** | | |

**Rollback:** Delete position_monitor.py, trade_tracker.py, governance/.

---

#### Sprint 4.4 — Health Monitor + Service (Day 52-56)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Write runtime/health_monitor.py — heartbeat, uptime, last scan | 2.0 | health_monitor.py | Heartbeat file updated |
| 2 | Write scripts/install.sh — pip install + systemd setup | 2.0 | install.sh | `bash scripts/install.sh` works |
| 3 | Write scripts/install.bat — Windows Task Scheduler | 1.0 | install.bat | Windows setup |
| 4 | Write tie-v4.service — systemd service file | 1.0 | service file | `systemctl start tie-v4` works |
| 5 | Update Makefile: service-install, service-start targets | 0.5 | Makefile | `make service-install` works |
| 6 | Fix #40: PID file management | 1.0 | fix | No orphan PIDs |
| 7 | Write tests/test_health_monitor.py | 1.0 | test file | Heartbeat age, uptime |
| 8 | Manual test: install on fresh VPS | 1.5 | verified | Engine starts, heartbeat current |
| **TOTAL** | | **10.0h** | | |

**Rollback:** Remove systemd service, delete health_monitor.py.

---

### PHASE 5: Dashboard + Observatory (Week 9)

#### Sprint 5.1 — Observatory (Day 57-59)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Extract gate_observatory.py to observatory/ | 2.0 | gate_observatory.py | Record + query works |
| 2 | Write postmortem.py — PostMortemAnalyzer | 2.0 | postmortem.py | Analyze closed trades |
| 3 | SQLite schema: gate_decisions + decision_traces tables | 1.0 | schema | Auto-create on first run |
| 4 | Timestamp filter (DB cumulative, not reset on restart) | 1.0 | filter | query_recent(minutes=2) works |
| 5 | Write tests/test_gate_observatory.py | 2.0 | test file | Record, query, timestamp filter |
| **TOTAL** | | **8.0h** | | |

**Rollback:** Delete observatory/.

---

#### Sprint 5.2 — Dashboard (Day 60-63)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Write dashboard/server.py — FastAPI app | 2.0 | server.py | `python -m tie_v4.dashboard` starts |
| 2 | Write routers/dashboard.py — all API endpoints | 3.0 | dashboard.py | All endpoints return data |
| 3 | Migrate static/ (index.html, app.js, style.css) | 2.0 | static files | Dashboard renders |
| 4 | Real-time gateway data via _gw_fetch() | 1.0 | gateway integration | Equity updates live |
| 5 | Strategy decode with _COMMENT_STRAT_MAP (fix #44) | 0.5 | decode | TIE_B_BUY → Bystra BUY |
| 6 | Write tests/test_dashboard_api.py | 2.0 | test file | Mock gateway, verify endpoints |
| **TOTAL** | | **10.5h** | | |

**Rollback:** Delete dashboard/.

---

### PHASE 6: Testing + Validation (Week 10)

#### Sprint 6.1 — Unit + Integration Tests (Day 64-67)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Write unit tests for ALL core modules | 6.0 | test files | `pytest` passes |
| 2 | Write integration test: mock data → full pipeline → decision | 3.0 | integration test | Pipeline end-to-end |
| 3 | Write adapter tests (mock + gateway with recorded responses) | 2.0 | adapter tests | All pass |
| 4 | Generate coverage report | 1.0 | report | >80% for core/ |
| 5 | Fix any failing tests | 2.0 | fixes | All green |
| **TOTAL** | | **14.0h** | | |

**Acceptance:**
- `pytest` passes all tests
- `pytest --cov=core/` shows >80% coverage
- No regressions from current behavior

---

#### Sprint 6.2 — Regression + Dry-Run (Day 68-70)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Dry-run test: `python -m tie_v4 --dry-run` against live gateway | 3.0 | dry-run log | Engine scans, logs, no trades |
| 2 | Compare decisions: V4 Portable vs V4 Production | 4.0 | comparison report | Same signal direction, SL, TP, lot |
| 3 | Performance benchmark: scan cycle < 5s | 2.0 | benchmark | Scan < 5s |
| 4 | Memory test: engine runs 24h without leak | 2.0 | memory report | RSS < 200MB after 24h |
| 5 | Fix any issues found | 3.0 | fixes | All green |
| **TOTAL** | | **14.0h** | | |

---

### PHASE 7: Deploy + Ship (Week 11)

#### Sprint 7.1 — Staging Deploy (Day 71-73)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Deploy to staging VPS (separate from production) | 2.0 | staging running | systemctl status |
| 2 | Run with real gateway, dry_run=True | 1.0 | dry-run live | Decisions logged |
| 3 | Monitor 48h: decisions, memory, stability | 2.0 | monitoring report | No crash, no leak |
| 4 | Fix any issues found | 3.0 | fixes | All stable |
| 5 | Document staging results | 1.0 | report | Reviewed |
| **TOTAL** | | **9.0h** | | |

---

#### Sprint 7.2 — Production Cutover (Day 74-77)

| # | Task | Hours | Output | Verify |
|---|------|-------|--------|--------|
| 1 | Stop old tie-production.service | 0.5 | stopped | `systemctl status` shows inactive |
| 2 | Close all open positions (manual on MT5 terminal) | 0.5 | no positions | `curl /account/positions` returns [] |
| 3 | Install V4 Portable as tie-v4.service | 1.0 | installed | `systemctl start tie-v4` works |
| 4 | Start with real money | 0.5 | running | First heartbeat logged |
| 5 | Monitor 24h: trades, trailing, dashboard | 3.0 | monitoring | All systems working |
| 6 | Update README.md with quick-start guide | 1.0 | README | Reviewed |
| 7 | Write CHANGELOG.md | 0.5 | CHANGELOG | Reviewed |
| 8 | Rollback test: verify old engine can still start | 1.0 | rollback verified | Old service starts |
| **TOTAL** | | **8.0h** | | |

**Rollback plan:**
1. `sudo systemctl stop tie-v4`
2. `sudo systemctl start tie-production`
3. Old code still in /home/ubuntu/trading-intelligence-engine/

---

## D. Sprint Summary Table (Consolidated)

| Sprint | Name | Days | Hours | Dependencies | Phase |
|--------|------|------|-------|--------------|-------|
| 1.1 | Package Skeleton + Config | 1-3 | 9.25 | None | 1 |
| 1.2 | Adapter Base + Mock | 4-6 | 11.25 | 1.1 | 1 |
| 1.3 | MT5 Gateway Adapter | 7-9 | 10.25 | 1.2 | 1 |
| 1.4 | MT5 Native + Docker | 10-14 | 9.75 | 1.3 | 1 |
| 2.1 | Features + Models | 15-17 | 8.50 | 1.1 | 2 |
| 2.2 | Regime + Opportunity | 18-20 | 9.50 | 2.1 | 2 |
| 2.3 | Context + Risk Rules | 21-23 | 13.00 | 2.1 | 2 |
| 2.4 | Strategy Interfaces | 24-28 | 10.50 | 2.3 | 2 |
| 3.1 | Bystra Migration | 29-31 | 15.00 | 2.4 | 3 |
| 3.2 | Aggressive Migration | 32-34 | 11.00 | 2.4 | 3 |
| 3.3 | SemiHFT Migration | 35-37 | 11.50 | 2.4 | 3 |
| 3.4 | Strategy Integration | 38-42 | 10.50 | 3.1+3.2+3.3 | 3 |
| 4.1 | Engine Core Loop | 43-45 | 14.50 | 2.4+3.4+1.3 | 4 |
| 4.2 | Trailing Consolidation | 46-48 | 12.00 | 4.1 | 4 |
| 4.3 | Position Monitor + Tracker | 49-51 | 11.00 | 4.2 | 4 |
| 4.4 | Health Monitor + Service | 52-56 | 10.00 | 4.3 | 4 |
| 5.1 | Observatory | 57-59 | 8.00 | 4.3 | 5 |
| 5.2 | Dashboard | 60-63 | 10.50 | 5.1 | 5 |
| 6.1 | Unit + Integration Tests | 64-67 | 14.00 | All Phase 1-5 | 6 |
| 6.2 | Regression + Dry-Run | 68-70 | 14.00 | 6.1 | 6 |
| 7.1 | Staging Deploy | 71-73 | 9.00 | 6.2 | 7 |
| 7.2 | Production Cutover | 74-77 | 8.00 | 7.1 | 7 |
| **TOTAL** | | **77 days** | **253.5h** | | |

> **Active work hours:** ~253.5h coding+testing+docs across 11 weeks ≈ 23h/week.
> **Wall-clock with parallelization:** ~180-200h (Phase 3 sprints 3.1-3.3 can overlap).

---

## E. Acceptance Criteria Checklist (All Phases)

### Phase 1 — Foundation
- [ ] `pip install -e .` succeeds on Linux
- [ ] `python -m tie_v4 --config config/engine.yaml` prints resolved config
- [ ] `${MT5_GATEWAY_URL}` resolves from env var
- [ ] `grep -rn "/home/ubuntu" tie_v4/` returns 0 matches
- [ ] Mock broker: submit/modify/close/positions/account all work
- [ ] Gateway adapter: get_account() returns real data from production
- [ ] Registry auto-detect: mock/gateway/native selection works

### Phase 2 — Core
- [ ] FeatureEngine.compute() returns valid FeatureSnapshot
- [ ] snapshot.atr is Dict[str, float] (NOT float)
- [ ] hasattr(snapshot, 'current_price') is False
- [ ] RegimeEngine detects TRENDING/RANGING/CHOPPY correctly
- [ ] OpportunityEngine: ASIA XAUUSD → blocked, LONDON → open
- [ ] RiskRegistry: all rules configurable from YAML
- [ ] TPValidation: SELL TP above entry → REJECT
- [ ] DynamicLot: equity $300 → 0.01

### Phase 3 — Strategy
- [ ] All 3 strategies importable and callable
- [ ] Bystra: 14 detectors all work
- [ ] Aggressive: entry_zone never {0,0}
- [ ] SemiHFT: MIN_ENTRY_SCORE=60 from config
- [ ] MultiStrategyRuntime.fuse() merges correctly
- [ ] Dedup: same direction within 120s → rejected
- [ ] All strategy codes map to correct order comments

### Phase 4 — Runtime
- [ ] TIEEngine.run() completes one scan cycle
- [ ] Heartbeat written to data/heartbeat.txt
- [ ] `touch data/halt` → engine stops
- [ ] Trailing: only ONE system modifies positions
- [ ] modify_order() always sends (sl, tp) pair
- [ ] Day-start dual-write works
- [ ] Weekend guard: no reset on Sat/Sun
- [ ] systemd service: start/stop/status works

### Phase 5 — Dashboard
- [ ] Observatory: record + query + timestamp filter
- [ ] Dashboard: all API endpoints return data
- [ ] Strategy decode: TIE_B_BUY → "Bystra BUY"
- [ ] Session header shows correct session from UTC hour

### Phase 6 — Testing
- [ ] `pytest` passes all tests
- [ ] Coverage >80% for core/
- [ ] Dry-run: engine scans, logs, no real trades
- [ ] Decision match: same signal as production
- [ ] Memory: RSS < 200MB after 24h

### Phase 7 — Deploy
- [ ] Staging runs 48h without crash
- [ ] Production cutover: first trade executed correctly
- [ ] Dashboard shows real-time data
- [ ] Rollback verified: old engine can still start

---

*Addendum created by Riri. Pending Boskuh review before merge into main doc.*
