# Dependency Audit Report — Sprint 5.8

## Audit Date: 2026-07-30
## Scope: TIE (`/home/ubuntu/trading-intelligence-engine`)

---

## 1. Legacy Imports in TIE

**Result: ZERO legacy imports found.**

Grep scan for: `brain`, `riri_sdk`, `BystraDetector`, `DecisionBrain`, `MarketBrain`, `RiskBrain`, `PositionBrain`

```
$ grep -rn "brain|riri_sdk|BystraDetector" /home/ubuntu/trading-intelligence-engine --include="*.py"
(no results)
```

TIE is clean. No Runtime, Detector, or Rule module imports from `riri_sdk/`.

---

## 2. Legacy Component Location

Legacy code lives at: `/home/ubuntu/.hermes/trading/riri_sdk/`
This path is **outside** TIE — no cross-dependency exists.

---

## 3. Components Identified for Archive

| Component | Path | Status |
|-----------|------|--------|
| MarketBrain | `riri_sdk/brains/market_brain.py` | Archive candidate |
| DecisionBrain | `riri_sdk/brains/decision_brain.py` | Archive candidate |
| RiskBrain | `riri_sdk/brains/risk_brain.py` | Archive candidate |
| PositionBrain | `riri_sdk/brains/position_brain.py` | Archive candidate |
| SetupBuilder | `riri_sdk/brains/setup_builder.py` | Archive candidate |
| news_filter | `riri_sdk/skills/news_filter.py` | REPLACED by TIE NewsFilterPlugin |
| dynamic_lot | `riri_sdk/skills/dynamic_lot.py` | REPLACED by TIE DynamicLotPlugin |
| adaptive_drawdown | `riri_sdk/skills/adaptive_drawdown.py` | REPLACED by TIE AdaptiveDrawdownPlugin |
| dynamic_daily_target | `riri_sdk/skills/dynamic_daily_target.py` | REPLACED by TIE DailyTargetPlugin |
| session_filter | `riri_sdk/skills/session_filter.py` | REPLACED by TIE SessionRule |
| trailing_stop | `riri_sdk/skills/trailing_stop.py` | KEPT in Runtime (ContractExecutor) |
| atr_calculator | `riri_sdk/skills/atr_calculator.py` | KEPT in Context Engine |
| trading_runtime_v2 | `riri_sdk/runtime/trading_runtime_v2.py` | REPLACED by TIE ExecutionRuntime |

---

## 4. Archive Note

Legacy files NOT physically moved (per sprint rules).
Archive is a logical designation.
Physical move scheduled for Sprint 5.9 (full regression passed).
