# Bystra Knowledge Pack v1.0

**Status:** 🔒 LOCKED  
**Version:** 1.0.0  
**Release:** Production  
**Compatible Engine:** TIE v1.x

---

## What is Bystra Pack?

Bystra Knowledge Pack is the first official Knowledge Pack for the Trading Intelligence Engine (TIE). It encodes the **Bystra Secret Strategy** by Nora — a price-action scalping framework for XAUUSD.

Knowledge Pack contains no detector logic, no trading rules, and no Python strategy code. It is pure structured knowledge — concepts, structures, locations, confirmations, risks, entry patterns, and setup definitions.

---

## Pack Contents

| Category | Count |
|---|---|
| Concepts | 50 |
| Structures | 15 |
| Locations | 21 |
| Confirmations | 26 |
| Risks | 23 |
| Entry Patterns | 16 |
| Setups | 13 |
| **Total** | **164** |

---

## Categories

- **Concepts** — Core vocabulary: impulse, retracement, liquidity, engulfing, etc.
- **Structures** — Price shapes: RBR, DBD, RBD, DBR, Quasimodo, Double Top, etc.
- **Locations** — Chart positions: Support V, Resistance V, Demand Zone, Fresh Zone, etc.
- **Confirmations** — Confluence signals: HTF Alignment, CK1/CK2/CK3, Engulfing, Liquidity Sweep, etc.
- **Risks** — Risk conditions: High Volatility, News Event, Stop Hunt, Broken Structure, etc.
- **Entry Patterns** — Entry triggers: RBR Breakout, Retest, Rejection, Demand Reaction, etc.
- **Setups** — 13 Bystra setups: Hybrid1/2, SNRC1/2/3, QMR, QMC, QM2P, QMM, Blindspot 1/2, Manipulation, CLAB

---

## Supported Setups

| ID | Name | Type | Risk |
|---|---|---|---|
| 001 | Hybrid 1 | Reversal | Medium |
| 002 | Hybrid 2 | Reversal | Medium |
| 003 | SNRC1 | Continuation | Low |
| 004 | SNRC2 | Continuation | Low |
| 005 | SNRC3 | Continuation | Medium |
| 006 | QMR | Reversal | High |
| 007 | QMC | Continuation | Medium |
| 008 | QM2P | Reversal | High |
| 009 | QMM | Reversal | High |
| 010 | Blindspot | Reversal | High |
| 011 | Blindspot 2 | Reversal | High |
| 012 | Manipulation | Reversal | Very High |
| 013 | CLAB | Confirmation | — |

---

## How TIE Uses This Pack

```
KnowledgeLoader → load YAML → Registry
Registry → GraphBuilder → KnowledgeGraph
KnowledgeGraph → QueryEngine → find/explain/dependencies
SetupEngine → evaluate FactSet against Setup definitions
DecisionEngine → BUY/SELL/WAIT based on SetupResult
```

Pack loaded via `PackLoader.load("knowledge/bystra")`.

---

## Compatibility

- **Engine:** TIE v1.x
- **Markets:** XAUUSD
- **Timeframes:** M5, M15, H1, H4
- **Strategy:** Bystra Secret Strategy by Nora

---

## Version History

| Version | Date | Notes |
|---|---|---|
| 1.0.0 | 2026-07-30 | Initial release — 164 objects, 13 setups |

---

## Known Limitations

- CLAB (Setup 013) is a confirmation method, not a standalone setup — `allowed_entry_patterns` marked TODO.
- Some `invalidate_conditions` fields in Setups 005, 007, 008, 013 marked TODO (not documented in source).
- Orphan objects (65 warnings) = valid objects not yet referenced by any Setup via BYS-ID. Will reduce as Detector Layer is built.
- Entry Patterns use `category: Concept` (TIE schema only supports 6 categories). Detector Layer will add proper `Entry Pattern` category support.

---

*Built for Boskuh. XAUUSD scalping with discipline.*
