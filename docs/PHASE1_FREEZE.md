# TIE Phase 1 — FREEZE DOCUMENT

**Architecture Version:** 1.0  
**Date:** 2026-07-30  
**Status:** 🔒 LOCKED

---

## Folder Structure

```
trading-intelligence-engine/
├── core/
│   ├── schema/          # knowledge_schema.yaml, schema_validator.py
│   ├── compiler/        # knowledge_loader.py
│   ├── relationships/   # relationship.py, relationship_types.py, relationship_validator.py
│   ├── graph/           # knowledge_graph.py, graph_builder.py, graph_validator.py
│   ├── context/         # context_model.py, context_engine.py, context_registry.py
│   ├── detectors/       # detector_interface.py, detector_engine.py, detector_registry.py, fact.py
│   ├── facts/           # factset.py, facts_engine.py, fact_registry.py, fact_validator.py, fact_resolver.py
│   ├── setup/           # setup_engine.py, setup_result.py, rule_evaluator.py, setup_registry.py, setup_validator.py
│   ├── decision/        # decision.py, execution_plan.py, decision_engine.py, decision_registry.py, decision_validator.py
│   ├── explanation/     # explanation_report.py, explanation_engine.py, explanation_builder.py
│   └── runtime/         # core_pipeline.py, pipeline_health.py, pipeline_runner.py
├── knowledge/           # Knowledge Packs (bystra/, ict/, smc/, crt/, custom/)
├── docs/
│   └── PHASE1_FREEZE.md
├── tests/
└── BLUEPRINT.md
```

---

## Public API (Core Contracts)

| Module | Class | Input | Output |
|--------|-------|-------|--------|
| compiler | `KnowledgeLoader` | YAML path | `KnowledgeRegistry` |
| graph | `GraphBuilder` | `KnowledgeRegistry` + `List[Relationship]` | `KnowledgeGraph` |
| context | `ContextEngine` | market data dict | `MarketContext` |
| detectors | `DetectorEngine` | `MarketContext` | `List[Fact]` |
| facts | `FactsEngine` | `List[Fact]` | `FactSet` |
| setup | `SetupEngine` | `FactSet` | `List[SetupResult]` |
| decision | `DecisionEngine` | `List[SetupResult]` | `List[Decision]` |
| explanation | `ExplanationEngine` | `FactSet` + `SetupResult` + `Decision` | `ExplanationReport` |
| runtime | `CorePipeline` | market data dict | `PipelineResult` |

---

## Module Responsibility (Single Sentence)

- **KnowledgeLoader:** Read YAML → validate → Python objects → Registry.
- **KnowledgeGraph:** Store nodes + directed edges; query relationships.
- **ContextEngine:** Raw market data → MarketContext (trend, session, ATR, spread, volatility).
- **DetectorEngine:** Orchestrate detector plugins → aggregate Facts.
- **FactsEngine:** Deduplicate + validate + resolve conflicts → FactSet.
- **SetupEngine:** Evaluate FactSet against Knowledge Pack rules → PASS/FAIL.
- **DecisionEngine:** SetupResult → BUY/SELL/WAIT + ExecutionPlan.
- **ExplanationEngine:** Facts + Setup + Decision → deterministic audit trail.
- **CorePipeline:** Wire all engines; run full pipeline; record timings.

---

## Dependency Rules

```
KnowledgeLoader  ← no dependency on any engine
GraphBuilder     ← depends on KnowledgeLoader output only
ContextEngine    ← no dependency on Graph/Loader
DetectorEngine   ← depends on ContextEngine output only
FactsEngine      ← depends on DetectorEngine output only
SetupEngine      ← depends on FactsEngine + SetupRegistry (compiled objects, NOT YAML)
DecisionEngine   ← depends on SetupEngine output only
ExplanationEngine← depends on Facts + Setup + Decision output only
CorePipeline     ← orchestrates all; no external I/O
```

**Golden Rules (enforced):**
- Loader owns YAML. No other module reads YAML.
- Detector outputs Facts only — no BUY/SELL/entry/SL/TP.
- Setup outputs PASS/FAIL only — no BUY/SELL.
- Decision is the only layer that outputs BUY/SELL/WAIT.
- Explanation never modifies Decision.
- No circular imports between core modules.
- Core Engine has zero knowledge of Bystra, ICT, SMC, CRT.

---

## Breaking Change Policy

After Phase 1 Freeze:

1. **Bug fix** — allowed without Blueprint change.
2. **Public API signature change** — requires Blueprint v1.1 + approval.
3. **New Core module** — requires Blueprint v1.1 + approval.
4. **Rename existing module** — requires Blueprint v1.1 + approval.
5. **Knowledge Pack changes** — free; Core Engine unaffected by design.

Phase 2 work (Knowledge Packs) MUST NOT modify any file under `core/`.

---

**Phase 1: COMPLETE ✅**  
**Next: Phase 2 — Bystra Knowledge Pack**
