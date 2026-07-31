# Signal Contract Migration Plan

## Current State (Pre-Migration)

**Detectors** currently return heterogeneous dicts with mixed responsibilities:
- Some include SL/TP
- Some include execution params
- Different field names
- No standard contract

## Target State

**Every detector returns `Signal`** — immutable, pure intent only.

```python
# OLD (detector.detect returns)
return {
    "direction": "BUY",
    "entry": 2041.0,
    "sl": 2038.5,
    "tp": 2050.0,
    "confidence": 0.75,
    "metadata": {...}
}

# NEW (detector.detect returns)
return Signal(
    signal_id="SNRC1_XAUUSD_20260731_143000",
    strategy="SNRC1",
    symbol="XAUUSD",
    direction=Direction.BUY,
    entry_zone={"low": 2040.0, "high": 2042.0},
    confidence=0.78,
    timeframe="M5",
    regime="TRENDING",
    opportunity_priority=6,
    metadata={"detector": "SNRC1", "base_zone": [2038, 2042]}
)
```

---

## Migration Steps

### Phase 1: ✅ DONE — Signal Contract
- `core/signals/signal.py` — Signal, Direction, SignalStatus, SignalBatch
- `core/signals/__init__.py` — Public API

### Phase 2: 🔄 UPDATE Detectors (one by one)

**Pattern for each detector:**

```python
# OLD
def detect(self, context: DetectorContext) -> List[Dict]:
    # ... logic ...
    return [{
        "direction": "BUY",
        "entry": entry_price,
        "sl": sl_price,
        "tp": tp_price,
        "confidence": conf,
        "metadata": {...}
    }]

# NEW
from core.signals import Signal, Direction

def detect(self, context: DetectorContext) -> List[Signal]:
    # ... logic (same) ...
    return [Signal(
        signal_id=f"{self.name}_{sym}_{int(time.time())}",
        strategy=self.name,
        symbol=sym,
        direction=Direction.BUY,
        entry_zone={"low": zone_low, "high": zone_high},
        confidence=conf,
        timeframe="M5",
        regime=context.metadata.get("regime", "UNKNOWN"),
        opportunity_priority=context.metadata.get("opportunity_priority", 0),
        metadata={"detector": self.name, "base_zone": [base_low, base_high]}
    )]
```

**Detectors to migrate (14):**
1. `snrc1_detector.py`
2. `snrc2_detector.py`
3. `snrc3_detector.py`
4. `hybrid1_detector.py`
5. `hybrid2_detector.py`
6. `manipulation_detector.py`
7. `qmr_detector.py`
8. `qmc_detector.py`
9. `qmm_detector.py`
10. `qm2p_detector.py`
11. `blindspot_detector.py`
12. `blindspot2_detector.py`
13. `clab_detector.py`
14. `mother_candle_detector.py`

### Phase 3: 🔄 UPDATE Orchestrator

**File: `strategy/orchestrator.py`**

```python
# OLD
def evaluate(self, context: DetectorContext) -> List[ExecutionContract]:
    signals = []
    for detector in self.detectors:
        for sig in detector.detect(context):
            # Convert to ExecutionContract with SL/TP
            exec_contract = self._build_execution(sig, context)
            signals.append(exec_contract)
    return signals

# NEW
from core.signals import Signal

def evaluate(self, context: DetectorContext) -> List[Signal]:
    """Returns pure Signals. SL/TP added later by ContractBuilder."""
    signals: List[Signal] = []
    for detector in self.detectors:
        for sig in detector.detect(context):
            # Enrich with context
            sig = sig._replace(
                regime=context.metadata.get("regime", "UNKNOWN"),
                opportunity_priority=context.metadata.get("opportunity_priority", 0)
            )
            signals.append(sig)
    return signals
```

**Add `ContractBuilder` class:**
```python
class ContractBuilder:
    """Converts Signal → ExecutionContract (adds SL/TP/Execution)."""
    
    def build(self, signal: Signal, context: DetectorContext) -> ExecutionContract:
        sl = self._calc_sl(signal, context)
        tp = self._calc_tp(signal, context)
        return ExecutionContract(
            signal_id=signal.signal_id,
            strategy=signal.strategy,
            symbol=signal.symbol,
            direction=signal.direction,
            entry_zone=signal.entry_zone,
            sl=sl,
            tp=tp,
            confidence=signal.confidence,
            # ... execution params
        )
```

### Phase 4: 🔄 UPDATE ContractExecutor / PositionMonitor

**ExecutionContract** now built by `ContractBuilder`, not by detectors.

`ContractExecutor.evaluate()` receives `ExecutionContract` with SL/TP already set.

### Phase 5: 🔄 UPDATE tie_production.py

```python
# Scan loop
signals = orchestrator.evaluate(context)  # Returns List[Signal]

# Filter by opportunity
if opportunity.market_allowed:
    for signal in signals:
        exec_contract = contract_builder.build(signal, context)
        # Risk gate validation
        if risk_gate.check(exec_contract, context):
            entry_monitor.queue(exec_contract)
```

---

## Compatibility Layer (Optional)

If gradual migration needed, add adapter:

```python
# core/signals/adapter.py
def signal_to_legacy_dict(signal: Signal) -> Dict:
    """Convert Signal to legacy dict format for backward compat."""
    return {
        "direction": signal.direction.value.upper(),
        "entry": signal.entry_mid,
        "entry_zone": signal.entry_zone,
        "confidence": signal.confidence,
        "strategy": signal.strategy,
        "symbol": signal.symbol,
        "timeframe": signal.timeframe,
        "metadata": signal.metadata,
    }

def legacy_dict_to_signal(d: Dict) -> Signal:
    """Convert legacy dict to Signal."""
    return Signal(
        signal_id=d.get("signal_id", f"{d['strategy']}_{d['symbol']}_{int(time.time())}"),
        strategy=d["strategy"],
        symbol=d["symbol"],
        direction=Direction(d["direction"].lower()),
        entry_zone=d.get("entry_zone", {"low": d["entry"], "high": d["entry"]}),
        confidence=d["confidence"],
        timeframe=d.get("timeframe", "M5"),
        metadata=d.get("metadata", {}),
    )
```

---

## Benefits

1. **Separation of concerns** — Detectors = signal generation only
2. **Testability** — Pure signal logic, no SL/TP math in detectors
3. **Composability** — Multiple signals from same detector, unified pipeline
4. **Auditability** — Signal lifecycle: RAW → VALIDATED → EXECUTED/EXPIRED/CANCELLED
5. **Reusability** — Same Signal contract works for all strategies

---

## Timeline

| Phase | Task | Effort |
|-------|------|--------|
| 1 | ✅ Signal Contract | Done |
| 2 | Update 14 detectors | 2-3 hours |
| 3 | Update Orchestrator + ContractBuilder | 1-2 hours |
| 4 | Update ContractExecutor/PositionMonitor | 30 min |
| 5 | Update tie_production.py integration | 30 min |
| **Total** | | **4-6 hours** |

---

## Validation

After migration:
- All detectors return `Signal` (type-checked)
- Orchestrator returns `List[Signal]`
- ContractBuilder creates `ExecutionContract` with SL/TP
- Risk gate validates `ExecutionContract`
- EntryMonitor/ContractExecutor unchanged interface

Run test suite: `pytest tests/ -v` — verify no regressions.