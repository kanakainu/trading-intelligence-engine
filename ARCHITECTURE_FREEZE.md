# Architecture Freeze — TIE v1.1.0-RC1 (HCK Integration)

**Date:** 2026-07-30
**Blueprint Version:** 1.1
**Repository Version:** 1.1.0-RC1

---

## Phase 6 Modules (NEW — FROZEN)

| Module | Files | Role |
|--------|-------|------|
| `adapters/hck_bridge.py` | 7 | TIE ↔ HCK boundary |
| `core/context/immutable_context.py` | 1 | Frozen context object |
| `core/context/context_cache.py` | 1 | Session-scoped cache |
| `core/context/context_injector.py` | 1 | HCK → Context builder |
| `core/context/context_validator.py` | 1 | Health check |
| `runtime/trade_postmortem.py` | 1 | Post-close HCK writer |

## Frozen API Additions

### HCKBridge
```python
bridge = HCKBridge(workspace, agent_id)
bridge.initialize()
bridge.get_context(canonical_id, message="")
bridge.get_recent_episodes(canonical_id, limit=5)
bridge.get_semantic_memory(canonical_id, limit=10)
bridge.get_identity(lid)
bridge.get_goals(canonical_id)
bridge.write_episode(canonical_id, user_msg, bot_reply)
bridge.write_reflection(canonical_id, content, category)
bridge.publish_event(event_type, payload)
bridge.health_check()
bridge.close()
```

### CompilerBridge (extended)
```python
bridge = CompilerBridge(setup_defs, policy=None, hck_bridge=None)
```

### ExecutionService (extended)
```python
svc = ExecutionService(runtime, risk_registry=None, logger=None, hck_bridge=None)
```

## Frozen Modules (DO NOT MODIFY without RFC)
All Phase 3 `core/` modules remain frozen.
All `adapters/` modules frozen.
`runtime/compiler_bridge.py`, `runtime/execution_service.py` frozen (extended API).

## Known Limitations
- HCK must be running for live injection (graceful degrade when down)
- `correlation_filter` not wired
- No live broker adapter (mock only)

## Future Roadmap (Phase 7+)
- Live MT5 broker adapter
- Real market data feed
- Concrete strategy: SNRC_1
- Backtesting engine
- Dashboard/monitoring UI
- HCK health cron job
