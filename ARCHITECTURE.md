# TIE — Trading Intelligence Engine Architecture
**Version:** v1.1.0-RC2  
**Date:** 2026-07-31  
**Status:** Production Running

---

## Overview

TIE is a multi-symbol, rule-based scalping engine for XAUUSD/BTCUSD/GBPJPY implementing the **Bystra Secret Strategy** with full structural SL/TP/Danger Zone compliance, Mother Candle setup, adaptive trailing, partial TP, and early exit reversal detection.

### Key Principles
- **Architecture > Speed** — maintainable, auditable, testable
- **Maintainability > Clever** — stdlib first, no unnecessary deps
- **Structural > Fixed** — SL/TP/DZ from market structure, not fixed pips
- **Real-time > Batch** — 10s scan loop, 2s dashboard polling

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        TIE Production Runtime                    │
│  (runtime/tie_production.py — 10s loop, systemd service)        │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  MT5 Gateway │  │  Context     │  │  Strategy    │           │
│  │  (REST + WS) │──│  Engine      │──│  Orchestrator│           │
│  └──────────────┘  └──────────────┘  └──────┬───────┘           │
│         ▲                  ▲                 │                   │
│         │                  │                 ▼                   │
│         │         ┌────────────────┐  ┌──────────────┐           │
│         │         │ 9 Detectors    │  │  Risk Gate   │           │
│         │         │ (SNRC1-3,      │  │  (RR≥1.5,    │           │
│         │         │  Hybrid1-2,    │  │  SL/TP val,  │           │
│         │         │  Manipulation, │  │  DZ check,   │           │
│         │         │  QMR/QMM,      │  │  Confidence) │           │
│         │         │  QM2P, MC)     │  └──────┬───────┘           │
│         │         └────────────────┘         │                   │
│         │                                    ▼                   │
│         │                          ┌──────────────────┐          │
│         │                          │  Entry Monitor   │          │
│         │                          │  (Watchlist →    │          │
│         │                          │   Pullback →     │          │
│         │                          │   In Zone →      │          │
│         │                          │   Reaction)      │          │
│         │                          └────────┬─────────┘          │
│         │                                   │                    │
│         ▼                                   ▼                    │
│  ┌──────────────────┐            ┌──────────────────┐           │
│  │ Position Monitor │            │  Contract        │           │
│  │ (per tick)       │            │  Executor        │           │
│  └────────┬─────────┘            └────────┬─────────┘           │
│           │                               │                     │
│           ▼                               ▼                     │
│  ┌──────────────────────────────────────────────────┐           │
│  │           MT5 Broker Adapter (order exec)        │           │
│  └──────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Dashboard (HTTP Polling)                      │
│  /api/status ← tie_status.json ← TIE writes every loop          │
│  Frontend: index.html polls /api/status every 2s                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. MT5 Gateway (`gateway_client.py`)
- **REST**: `/price`, `/candles`, `/positions`, `/account`, `/order`
- **WebSocket**: Real-time price stream (backup)
- **Broker Adapter**: `MT5BrokerAdapter` — normalize MT5 → internal models

### 2. Context Engine (`core/context/context_engine.py`)
Builds `MarketContext` per symbol per scan:
- Multi-TF candles (M5, M15, M30, H1)
- ATR (H1, 14-period)
- H1 Support/Resistance (nearest swing pivots to current price)
- H1 Trend (bullish/bearish)
- Spread, session, balance, equity

### 3. Detectors (14 Active)
| Detector | Setup | TF | Key Logic |
|----------|-------|-----|-----------|
| SNRC1 | Support/Resistance + Candle | M5/M15 | Base zone, retest, engulfing |
| SNRC2 | SR + Candle v2 | M5/M15 | Different confirmation |
| SNRC3 | SR + Candle v3 | M5/M15 | Strongest SR + candle |
| Hybrid1 | SR + Trend + Candle | M5/M15 | Multi-confluence |
| Hybrid2 | SR + Trend + Candle v2 | M5/M15 | Different weights |
| Manipulation | HTF Engulfing | H1→M5 | HTF engulf + M5 entry |
| QMR | Quasimodo Reversal | M5/M15 | Head/shoulders structure |
| QMC | Quasimodo Confirmation | M5/M15 | QM with confirmation |
| QM2P | QM 2-Pattern | M5/M15 | Double QM |
| QMM | Quasimodo Momentum | M5/M15 | Momentum variant |
| Blindspot | Blindspot Pattern | M5/M15 | Hidden liquidity + reaction |
| Blindspot_2 | Blindspot v2 | M5/M15 | Variant with different filter |
| CLAB | Clab Pattern | M5/M15 | Consolidation + breakout |
| **Mother Candle** | **NEW** | **H1** | **1 MC shadows 4 inside, B1/B2/B3 breakout** |

**Output per detector:** `PatternFact` with metadata:
```python
{
  "direction": "BUY|SELL",
  "entry_zone": {"high": float, "low": float},
  "sl": float,                    # structural SL (entry_tf swing)
  "tp": float,                    # nearest H1 S/R with ≥1.5 RR
  "danger_zone": float,           # per-setup invalidation level
  "entry_tf": "M5|M15|H1",        # entry timeframe
  "confidence": 0.55-0.95
}
```

### 4. Strategy Orchestrator (`strategy/orchestrator.py`)
- Selects best fact by confidence
- **SL Calculation:** Swing pivot on `entry_tf` candles
  - SELL: nearest swing HIGH **above entry_zone** + buffer
  - BUY: nearest swing LOW **below entry_zone** - buffer
- **TP Calculation:** Nearest H1 S/R in trade direction
  - SELL: nearest H1 support below entry
  - BUY: nearest H1 resistance above entry
  - Min RR 1:1.5, fallback = entry ± (risk × 1.5)
- **Danger Zone:** Uses detector's `danger_zone` if set, else H1 S/R fallback
- Returns `TradeDecision` with full metadata

### 5. Risk Gate (`core/rules/risk/`)
Plugins (all must APPROVE):
| Rule | Check |
|------|-------|
| `min_risk_reward` | RR ≥ 1.5 |
| `sl_validation` | SL outside entry_zone (SELL: SL > entry_zone.high) |
| `tp_validation` | TP in correct direction (SELL: TP < entry) |
| `danger_zone` | Price not touching DZ |
| `confidence_gate` | Confidence ≥ 0.55 |
| `session_rule` | Not in dead zone |
| `spread_rule` | Spread ≤ threshold |
| `daily_target` | Halt if $30 reached |
| `daily_loss_limit` | Halt if -$100 |
| `max_drawdown` | 5% equity DD halt |
| `max_open_positions` | ≤ 8 total |
| `max_position_size` | ≤ 0.1 lot |
| `duplicate_prevention` | Same setup/symbol/direction dedup 5min |

### 6. Entry Monitor (`runtime/entry_monitor.py`)
State machine per setup:
```
PENDING_PULLBACK → IN_ZONE → REACTION_CONFIRMED → EXECUTED
```
- Pullback: price enters `entry_zone`
- Reaction: **TODO** — currently basic (price stays in zone). Bystra requires M1 engulfing/wick rejection.

### 7. Contract Executor (`runtime/contract_executor.py`)
Evaluates live positions each tick via `PositionMonitor`:

| Feature | Config | Logic |
|---------|--------|-------|
| **Breakeven** | `be_trigger_atr=1.0` | Move SL to entry + buffer at 1.0 ATR profit |
| **Adaptive Trailing** | `trail_trigger_atr=1.5`, `trail_offset_atr=0.5` | Market structure (S/R) + 0.5 ATR buffer; fallback ATR offset |
| **Partial TP** | `partial_tp_pct=0.5` | Close 50% volume at 50% TP distance |
| **Early Exit Reversal** | `early_exit_reversal=True` | **M5 closed candles only** — engulfing (1.2× body) or consecutive same-direction (0.8× body). **NO M1** |

### 8. Dashboard (`/home/ubuntu/tie-dashboard/`)
- **Backend:** FastAPI `api/tie_serve.py` on port 3001
  - `GET /` → index.html
  - `GET /api/status` → reads `tie_status.json` fresh
- **Frontend:** Vanilla JS, polls `/api/status` every 2s
- **Data:** Multi-pair grid (XAUUSD, BTCUSD, GBPJPY) + fresh setups only + positions + account + gateway status

---

## Data Flow

```
1. TIE Loop (10s)
   ├─ For each symbol:
   │   ├─ Fetch M5/M15/M30/H1 candles (40/20/20/20)
   │   ├─ Fetch price, spread, account, positions
   │   ├─ Build MarketContext (ATR, H1 S/R, trend)
   │   ├─ Run 9 detectors → PatternFacts
   │   ├─ Orchestrator → best TradeDecision (SL/TP/DZ)
   │   ├─ Risk Gate → APPROVE/BLOCK
   │   ├─ If PASS: EntryMonitor.add_setup()
   │   └─ PositionMonitor.tick() with M5 candles
   └─ Write tie_status.json (accumulates all pairs)

2. Dashboard (2s poll)
   ├─ GET /api/status
   ├─ Render pairs grid with setup badges
   ├─ Render fresh setups (setup !== null)
   ├─ Render positions with P&L
   └─ Render account/gateway

3. Order Execution
   ├─ EntryMonitor detects reaction
   ├─ Market order via MT5BrokerAdapter (0.01 lot)
   ├─ Position created in tracker
   └─ ContractExecutor manages lifecycle
```

---

## Configuration

### Risk Config (`risk/config.py`)
```python
policies = {
    "max_position_size":     {"max_volume": 0.1},      # per position
    "max_open_positions":    {"max_count": 8},         # total
    "daily_loss_limit":      {"max_loss_usd": 100.0},
    "maximum_drawdown":      {"max_drawdown_percent": 0.05},
    "margin_availability":   {"min_free_margin_percent": 0.1},
    "minimum_risk_reward":   {"min_rr": 1.5},
    "market_availability":   {},
    "duplicate_position_prevention": {},
}
```

### Symbols (`runtime/tie_production.py`)
```python
SYMBOLS = ['XAUUSD', 'BTCUSD', 'GBPJPY']
```

### Execution Contract Defaults (`runtime/tie_production.py`)
```python
metadata = {
    'be_trigger_atr': 1.0,
    'trail_trigger_atr': 1.5,
    'trail_offset_atr': 0.5,
    'partial_tp_pct': 0.5,
    'early_exit_reversal': True,
}
```

---

## Deployment

### VPS
- **IP:** 43.156.47.33 (Tencent SG)
- **OS:** Ubuntu 22.04
- **Python:** 3.11+

### Services
```bash
# TIE Production
systemctl --user start tie-production
systemctl --user status tie-production
journalctl --user -u tie-production -f

# Dashboard
cd /home/ubuntu/tie-dashboard && python3 api/tie_serve.py &
# Access: http://43.156.47.33:3001
```

### Ports
- **3001** — Dashboard API + Frontend (HTTP polling)
- **8766** — DEPRECATED (WebSocket, blocked by firewall)
- **3000** — WA Bridge (internal)

---

## Bystra Compliance Checklist

| Rule | Status | Location |
|------|--------|----------|
| SL from entry_tf swing pivot | ✅ | `orchestrator.py:83-110` |
| TP = nearest H1 S/R, min 1.5 RR | ✅ | `orchestrator.py:115-145` |
| DZ = per-setup invalidation | ✅ | Detector metadata → orchestrator |
| SL buffer = spread + structural | ✅ | `sl_buffer()` per pair |
| Mother Candle: 1 MC, 4 inside, B1/B2/B3 | ✅ | `mother_candle_detector.py` |
| No M1 for decisions | ✅ | Early exit uses M5 closed only |
| Partial TP at 50% | ✅ | `contract_executor.py` |
| Adaptive trailing (structure + ATR) | ✅ | `contract_executor.py` |
| Early exit reversal (engulfing/consecutive M5) | ✅ | `contract_executor.py` |

---

## Known Gaps / TODO

1. **Entry Reaction Logic** — EntryMonitor reaction check is basic (price in zone). Need Bystra M1 engulfing/wick rejection confirmation.

2. **Regime Detector** — HMM regime wired but not feeding into orchestrator for filter.

3. **News Calendar** — ForexFactory/Investing fetch works but not gating trades fully.

4. **Learning Brain** — Post-trade analytics written to `logs/learning_insights.json`, LLM reasoner reads it but confidence boost not yet validated.

5. **GBPJPY vs GBPUSD** — Riri changed symbol; verify broker supports GBPJPY with same specs.

6. **Dashboard WebSocket** — Removed (firewall). HTTP polling works but higher latency. Consider SSE if needed.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v1.1.0-RC2 | 2026-07-31 | Full Bystra SL/TP/DZ, Mother Candle, adaptive trailing, partial TP, early exit M5, realtime dashboard multi-pair |
| v1.1.0-RC1 | 2026-07-31 | ATR real, HMM, dynamic trailing, Telegram, Calendar, Learning Brain, Trade Journal, Dashboard HTTP polling |
| v1.0.0 | 2026-07-30 | Initial production: detectors, orchestrator, risk gate, entry monitor, MT5 gateway |

---

## Files Reference

### Core Engine
- `runtime/tie_production.py` — Main loop, status writer
- `strategy/orchestrator.py` — Decision logic, SL/TP/DZ
- `runtime/entry_monitor.py` — Setup watchlist state machine
- `runtime/position_monitor.py` — Per-tick position evaluation
- `runtime/contract_executor.py` — Trailing, partial, early exit

### Detectors
- `detectors/common.py` — Utilities: swing pivots, S/R, buffers
- `detectors/snrc1_detector.py` ... `snrc3_detector.py`
- `detectors/hybrid1_detector.py`, `hybrid2_detector.py`
- `detectors/manipulation_detector.py`
- `detectors/qmr_detector.py`, `qmc_detector.py`, `qmm_detector.py`, `qm2p_detector.py`
- `detectors/blindspot_detector.py`, `blindspot2_detector.py`
- `detectors/clab_detector.py`
- `detectors/mother_candle_detector.py` — NEW

### Risk
- `risk/config.py` — Policies
- `core/rules/risk/risk_registry.py` — Plugin registry
- `core/rules/risk/*.py` — Individual rules

### Dashboard
- `/home/ubuntu/tie-dashboard/api/tie_serve.py` — FastAPI
- `/home/ubuntu/tie-dashboard/index.html` — Frontend
- `/home/ubuntu/tie-dashboard/data/tie_status.json` — Status file

### Infra
- `/home/ubuntu/.config/systemd/user/tie-production.service` — systemd unit
- `config/live.py` — Credentials (gitignored)

---

**End of Architecture Document**