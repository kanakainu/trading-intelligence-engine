# Aggressive Strategy

**Status:** Skeleton — not production-ready.

## Architecture

```
strategies/aggressive/
├── strategy.py      ← AggressiveStrategy(BaseStrategy)
├── metadata.py      ← identity + supported symbols
├── config.py        ← AggressiveConfig(StrategyConfig)
├── detectors/       ← TBD
├── filters/         ← TBD
├── exits/           ← TBD
└── tests/           ← TBD
```

## Lifecycle

`initialize()` → `observe()` → `analyze()` → `StrategyResult`

## Status

- [ ] Detector implementation
- [ ] Entry logic
- [ ] Exit logic
- [ ] Risk filters
- [ ] Tests
