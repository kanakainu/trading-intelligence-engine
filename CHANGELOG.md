# CHANGELOG — Trading Intelligence Engine

## [1.1.0-RC1] — 2026-07-30 — HCK Integration

### Phase 6 — HCK Bridge & Context Integration (NEW)
- 6.1 HCK Bridge: `adapters/hck_bridge.py` + memory_provider, context_provider, episode_writer, reflection_writer, semantic_reader, event_dispatcher
- 6.2 Pipeline HCK Integration: CompilerBridge injects episodic/semantic, ExecutionService writes episode + reads goals
- 6.3 HCK Live Test: verified PostgreSQL read/write
- 6.4 Context Injection: `immutable_context.py`, `context_cache.py`, `context_injector.py`, `context_validator.py`
- 6.5 Trade Postmortem: `runtime/trade_postmortem.py` — post-close HCK writer

### Metrics
- **794 tests passing** (vs 732 in v1.0.0-RC1)
- **249 Python files** (adapters deduped)
- **740 test functions**

## [1.0.0-RC1] — 2026-07-30 — Initial Release

### Phase 1-5
- Core Intelligence Compiler (Phase 3 FROZEN)
- Adapter Framework (Phase 4.1-4.4)
- Risk Layer (Phase 4.6)
- Position Manager (Phase 4.7)
- Skill Framework (Phase 4.8)
- Strategy Runtime (Phase 4.9)
- SDK Migration (Phase 4.10)
- Migration Phase 5 (5.1-5.10)
