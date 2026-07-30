# Legacy Cleanup Report — Sprint 5.8
## Date: 2026-07-30

---

## 1. Overview
TIE runtime has ZERO imports from legacy riri_sdk. All dependency cutover complete across Sprints 5.1–5.7.

---

## 2. Removed Modules (Logical Removal from TIE)

| Module | Legacy Path | TIE Replacement | Status |
|--------|-------------|-----------------|--------|
| MarketBrain | `riri_sdk/brains/market_brain.py` | `core/context/context_engine.py` + `core/facts/fact_compiler.py` | REPLACED |
| DecisionBrain | `riri_sdk/brains/decision_brain.py` | `core/decision/decision_pipeline.py` + `core/reasoning/reasoning_engine.py` | REPLACED |
| RiskBrain | `riri_sdk/brains/risk_brain.py` | `core/rules/risk/*.py` + `core/rules/plugins/*.py` | REPLACED |
| PositionBrain (intelligence) | `riri_sdk/brains/position_brain.py` | `runtime/contract_executor.py` + `runtime/position_manager.py` | REPLACED |
| SetupBuilder | `riri_sdk/brains/setup_builder.py` | `core/setup/setup_resolver.py` | REPLACED |
| trading_runtime_v2 | `riri_sdk/runtime/trading_runtime_v2.py` | `runtime/execution_runtime.py` + `runtime/execution_service.py` | REPLACED |
| BystraDetector (monolith) | `bystra_bot/core/detector.py` | `detectors/*.py` (13 files) | REPLACED |

---

## 3. Archived Files

Legacy code lives at: `/home/ubuntu/.hermes/trading/riri_sdk/`
NOT physically deleted. Archive manifest in `dependency_audit.md`.

---

## 4. Remaining Legacy Components

| Component | Path | Reason Kept |
|-----------|------|-------------|
| `position_brain.py` trailing/BE logic | `riri_sdk/brains/position_brain.py` | Superseded by `runtime/contract_executor.py`. Kept as regression reference. |
| `atr_calculator.py` | `riri_sdk/skills/atr_calculator.py` | Utility. Referenced by Context Engine. |
| `trailing_stop.py` | `riri_sdk/skills/trailing_stop.py` | Logic migrated to ContractExecutor. Kept as reference. |
| `correlation_filter.py` | `riri_sdk/skills/correlation_filter.py` | Execution Adapter candidate. Not yet wired. |

---

## 5. Cutover Checklist

| Check | Status |
|-------|--------|
| Runtime uses TIE | ✅ `execution_runtime.py` imports only TIE modules |
| Detector from TIE | ✅ `detectors/*.py` inherit `DetectorInterface` |
| Setup from TIE | ✅ `core/setup/setup_resolver.py` |
| Decision from TIE | ✅ `core/decision/decision_pipeline.py` |
| Rules from TIE | ✅ `core/rules/risk/*.py` + plugins |
| Execution uses Contract | ✅ `ExecutionContract` is sole input to `ExecutionRuntime` |
| No BUY/SELL in Runtime | ✅ Verified by import scan + test |
| No legacy import | ✅ grep scan = 0 results |
| Legacy archived | ✅ Physical files at `riri_sdk/` (not deleted) |
| Tests passing | ✅ 648+ passed |
