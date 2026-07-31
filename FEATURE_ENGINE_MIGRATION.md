# TIE v2 Feature Engine — Architecture & Migration Plan

## Folder Tree

```
core/features/
├── __init__.py           # Public API exports
├── feature_models.py     # FeatureSnapshot (immutable), FeatureInputs
├── feature_engine.py     # FeatureEngine — computes all features once per scan
└── feature_cache.py      # FeatureCache — TTL cache per symbol per scan
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TIE Scan Loop (10s)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Fetch candles (M1, M5, M15, H1) + tick + spread                │
│         │                                                           │
│         ▼                                                           │
│  2. FeatureInputs(symbol, candles, tick, spread, timestamp)        │
│         │                                                           │
│         ▼                                                           │
│  3. FeatureCache.get_or_compute(inputs)                             │
│         │                                                           │
│         ├── Cache HIT  ──► Return cached FeatureSnapshot            │
│         │                                                           │
│         └── Cache MISS ──► FeatureEngine.compute(inputs)            │
│                            │                                         │
│                            ├── EMA(8,9,13,21,34,50,200) × 4 TFs    │
│                            ├── EMA Slope(21,50) × 4 TFs             │
│                            ├── ATR(14) × 4 TFs                      │
│                            ├── True Range × 4 TFs                   │
│                            ├── Body/Wick Ratio × 4 TFs              │
│                            ├── Impulse Size × 4 TFs                 │
│                            ├── Momentum Score × 4 TFs               │
│                            ├── Volume MA/Ratio/Spike × 4 TFs        │
│                            ├── VWAP + Distance × 4 TFs              │
│                            ├── Swing High/Low × 4 TFs               │
│                            ├── Spread / Tick Speed / Price Velocity │
│                            │                                         │
│                            ▼                                         │
│                      FeatureSnapshot (immutable)                    │
│                            │                                         │
│                            ▼                                         │
│  4. Cache + Return FeatureSnapshot                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        14 DETECTORS (Read-Only)                     │
│                                                                     │
│  detector.detect(context)                                          │
│     │                                                               │
│     ├── context.metadata['features']  ──► FeatureSnapshot          │
│     │                                                               │
│     ├── features.get_ema("M5", 21)        ──► float               │
│     ├── features.get_atr("M5")            ──► float               │
│     ├── features.get_vwap("M5")           ──► float               │
│     ├── features.get_swing("M5", "high")  ──► float               │
│     ├── features.momentum_score["M5"]     ──► float               │
│     ├── features.body_ratio["M5"]         ──► float               │
│     ├── features.distance_to_vwap["M5"]   ──► float               │
│     ├── features.spread                   ──► float               │
│     └── features.candles["M5"]            ──► raw candles         │
│                                                                     │
│  ❌ NO detector calculates EMA/ATR/VWAP/Swings anymore             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. FeatureInputs (`feature_models.py`)
```python
@dataclass(frozen=True, slots=True)
class FeatureInputs:
    candles: Dict[str, List[Dict]]  # M1, M5, M15, H1
    current_tick: Optional[Dict] = None
    spread: float = 0.0
    symbol: str = ""
    timestamp: Optional[datetime] = None
```

### 2. FeatureSnapshot (`feature_models.py`) — **IMMUTABLE**
```python
@dataclass(frozen=True, slots=True)
class FeatureSnapshot:
    symbol: str
    timestamp: datetime
    scan_id: str
    
    # Accessor methods (convenience)
    def get_ema(self, timeframe: str, period: int) -> Optional[float]
    def get_ema_slope(self, timeframe: str, period: int) -> Optional[float]
    def get_atr(self, timeframe: str) -> Optional[float]
    def get_vwap(self, timeframe: str) -> Optional[float]
    def get_swing(self, timeframe: str, side: str) -> Optional[float]
    
    # Direct dict access also available:
    # features.ema["M5"]["ema21"]
    # features.atr["M5"]
    # features.body_ratio["M5"]
```

### 3. FeatureEngine (`feature_engine.py`)
```python
engine = FeatureEngine()
snapshot = engine.compute(inputs)  # Called once per scan
```

**Pure math helpers** (reusable):
- `_ema(values, period)` — Wilder's EMA
- `_atr(candles, period)` — Wilder's ATR
- `_compute_swings()` — 3-candle pivot detection

### 4. FeatureCache (`feature_cache.py`) — Thread-safe
```python
cache = get_feature_cache(ttl_seconds=15.0)
snapshot = cache.get_or_compute(inputs)  # Auto cache/compute

# Global convenience function
from core.features import compute_features
snapshot = compute_features(inputs)
```

---

## Migration Plan

### Phase 1: ✅ DONE — Feature Engine Core
- [x] `core/features/feature_models.py` — FeatureSnapshot, FeatureInputs
- [x] `core/features/feature_engine.py` — FeatureEngine with all indicators
- [x] `core/features/feature_cache.py` — FeatureCache with TTL
- [x] `core/features/__init__.py` — Public API
- [x] Unit test: computes all features correctly

### Phase 2: 🔄 IN PROGRESS — Wire into TIE Production
**File: `runtime/tie_production.py`**

```python
# ADD at top:
from core.features import compute_features, FeatureInputs

# IN scan loop, AFTER fetching candles:
from datetime import datetime

inputs = FeatureInputs(
    candles=candles,           # {'M1': [...], 'M5': [...], 'M15': [...], 'H1': [...]}
    current_tick=None,         # optional
    spread=spread,
    symbol=sym,
    timestamp=datetime.now(timezone.utc)
)

features = compute_features(inputs)

# ADD to context.metadata:
ctx.metadata["features"] = features
ctx.metadata["feature_scan_id"] = features.scan_id
```

### Phase 3: 🔄 PENDING — Update Context Engine
**File: `core/context/context_engine.py`** (if used)

```python
# ContextEngine.build() should include features in returned context.metadata
context.metadata["features"] = features
```

### Phase 4: 🔄 PENDING — Update Detectors (one by one)
**Pattern for each detector:**

```python
# OLD (inside detector.detect):
ema21 = self._ema(closes, 21)
atr = self._atr(candles, 14)
vwap = self._vwap(candles)

# NEW:
features = context.metadata.get("features")
if features:
    ema21 = features.get_ema("M5", 21)
    atr = features.get_atr("M5")
    vwap = features.get_vwap("M5")
    swing_high = features.get_swing("M5", "high")
    body_ratio = features.body_ratio.get("M5")
    # etc.
else:
    # Fallback: compute locally (temporary during migration)
    pass
```

**Detectors to migrate (14 total):**
1. `snrc1_detector.py` → uses EMA, ATR, swings
2. `snrc2_detector.py` → uses EMA, ATR, swings
3. `snrc3_detector.py` → uses EMA, ATR, swings
4. `hybrid1_detector.py` → uses EMA, ATR, swings, VWAP
5. `hybrid2_detector.py` → uses EMA, ATR, swings
6. `manipulation_detector.py` → uses ATR, swings
7. `qmr_detector.py` → uses swings, body/wick
8. `qmc_detector.py` → uses swings
9. `qmm_detector.py` → uses momentum
10. `qm2p_detector.py` → uses swings
11. `blindspot_detector.py` → uses ATR, swings, volume
12. `blindspot2_detector.py` → uses ATR, swings
13. `clab_detector.py` → uses ATR, swings
14. `mother_candle_detector.py` → uses ATR, swings (H1)

### Phase 5: 🔄 PENDING — Remove Duplicate Code
After all detectors migrated:
- Remove `_ema`, `_atr`, `_vwap`, `_swing` methods from each detector
- Remove `from detectors.common import find_swing_pivots` if no longer needed
- Keep `detectors/common.py` for: `sl_buffer`, `body_size`, `is_engulfing`, `check_retest`, `get_base_zone`

### Phase 6: 🔄 PENDING — Performance Validation
- Benchmark: scan loop time before/after
- Verify cache hit rate > 90%
- Memory profile: FeatureSnapshot size per symbol

---

## API Reference

### Compute Features
```python
from core.features import compute_features, FeatureInputs
from datetime import datetime

inputs = FeatureInputs(
    candles={"M5": [...], "M15": [...], "H1": [...]},
    spread=0.5,
    symbol="XAUUSD",
    timestamp=datetime.now()
)
features = compute_features(inputs)
```

### Access Features in Detector
```python
def detect(self, context):
    features = context.metadata.get("features")
    if not features:
        return []  # or fallback
    
    # Trend
    ema21 = features.get_ema("M5", 21)
    ema50 = features.get_ema("M5", 50)
    ema21_slope = features.get_ema_slope("M5", 21)
    
    # Volatility
    atr = features.get_atr("M5")
    atr_pct = features.atr_percent.get("M5")
    tr = features.true_range.get("M5")
    
    # Momentum
    body_ratio = features.body_ratio.get("M5")
    wick_ratio = features.wick_ratio.get("M5")
    impulse = features.impulse_size.get("M5")
    mom_score = features.momentum_score.get("M5")
    
    # Volume
    vol_ma = features.volume_ma.get("M5")
    vol_ratio = features.volume_ratio.get("M5")
    vol_spike = features.volume_spike.get("M5")
    
    # VWAP
    vwap = features.get_vwap("M5")
    dist_vwap = features.distance_to_vwap.get("M5")
    
    # Structure
    swing_high = features.get_swing("M5", "high")
    swing_low = features.get_swing("M5", "low")
    
    # Market
    spread = features.spread
    tick_speed = features.tick_speed
    price_vel = features.price_velocity
    
    # Raw candles (if needed)
    m5_candles = features.candles.get("M5", [])
```

---

## Performance Characteristics

| Metric | Target |
|--------|--------|
| Compute time (all features, 4 TFs, 100 candles each) | < 5ms |
| Cache hit rate (10s scan interval, 15s TTL) | > 95% |
| Memory per FeatureSnapshot | ~50 KB |
| Features per scan | ~200 values |

---

## Breaking Changes

**None** — Feature Engine is additive. Detectors continue working with fallback until migrated.

**Migration is opt-in per detector** — detectors check `context.metadata.get("features")` and use if available.

---

## Next Steps

1. **Wire into `tie_production.py`** — add FeatureInputs creation + `compute_features()` call
2. **Add to Context metadata** — `ctx.metadata["features"] = features`
3. **Migrate detectors one by one** — start with highest-impact (SNRC1, Hybrid1)
4. **Run full test suite** — verify no regression in detector outputs
5. **Benchmark** — confirm scan loop time improvement

---

**Status:** Phase 1 Complete ✅ | Phase 2 Ready to Implement