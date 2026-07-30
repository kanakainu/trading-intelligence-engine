# CHANGELOG — Bystra Knowledge Pack

## v1.0.0 — 2026-07-30 — Initial Release

### Added
- Ontology: 42 taxonomy objects across 13 categories
- Concepts: 50 core trading concepts (impulse, liquidity, engulfing, trend, zones, etc.)
- Structures: 15 price structures (RBR, DBD, RBD, DBR, Bull Flag, Bear Flag, Quasimodo, Double Top, etc.)
- Locations: 21 chart locations (Support V, Resistance V, Demand Zone, Supply Zone, Liquidity Pool, etc.)
- Confirmations: 26 confirmation signals (HTF Alignment, CK1/CK2/CK3, Engulfing, Liquidity Sweep, etc.)
- Risks: 23 risk conditions (High Volatility, News Event, Stop Hunt, Broken Structure, etc.)
- Entry Patterns: 16 entry triggers (RBR Breakout, Retest, Rejection, Demand Reaction, Liquidity Sweep Entry, etc.)
- Setups: 13 Bystra setup definitions extracted from Bystra Secret Strategy document
- Manifest, VERSION, PACK_INFO, README, CHANGELOG
- Pack Integrity SHA256 fingerprint

### Technical
- All objects validated against TIE schema
- Dependency graph validated (0 circular, 0 broken refs)
- Pack Loader + Integrity Checker implemented
- Knowledge Query Engine (10 API methods, 512-slot cache)

---

## Planned (v1.1.0)

- Fill TODO fields in Setups 005, 007, 008, 013
- Add `Entry Pattern` as first-class TIE schema category
- Reduce orphan warnings by wiring more objects to Setup requirements
- Detector Rules layer (separate pack or Phase 3)
