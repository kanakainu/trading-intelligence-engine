# Release Notes — TIE v1.1.0-RC1 (HCK Integration)
**Date:** 2026-07-30
**Status:** Release Candidate 1 — HCK Integration Complete

---

## What Changed Since v1.0.0-RC1

### New: HCK Bridge Layer
- `adapters/hck_bridge.py` — single boundary between TIE and HCK
- `adapters/memory_provider.py`, `context_provider.py`, `episode_writer.py`
- `adapters/reflection_writer.py`, `semantic_reader.py`, `event_dispatcher.py`

### New: Pipeline HCK Integration
- `CompilerBridge.compile()` — injects episodic + semantic memory before decide
- `ExecutionService.submit()` — writes episode to HCK after FILLED
- `ExecutionService.submit()` — reads HCK goals into risk context

### New: Context Injection
- `core/context/immutable_context.py` — frozen dataclass, read-only
- `core/context/context_cache.py` — session-scoped cache
- `core/context/context_injector.py` — HCK → ImmutableContext builder
- `core/context/context_validator.py` — health check for context completeness

### New: Trade Postmortem
- `runtime/trade_postmortem.py` — auto-writes WIN/LOSS/BREAKEVEN to HCK

### Metrics

| Item | v1.0.0-RC1 | v1.1.0-RC1 |
|------|------------|------------|
| Python files | 292 | 249 (deduped) |
| YAML knowledge | 177 | 177 |
| Test functions | 679 | 740 |
| Passed | 732 | 794 |

## Breaking Changes
- `CompilerBridge.__init__(setup_defs, policy, hck_bridge=None)` — hck_bridge param added (optional, backward compatible)
- `ExecutionService.__init__(runtime, risk_registry, logger, hck_bridge=None)` — hck_bridge param added

## Known Limitations
- HCK must be running for context injection (graceful degrade when down)
- `correlation_filter` not yet wired to Execution Adapter
- No live broker adapter (mock only)
