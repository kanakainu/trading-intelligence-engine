"""Sprint 5.9 — Replay: 1000x stress test without exception or memory leak."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import gc
import pytest
from datetime import datetime, timezone
from runtime.compiler_bridge import CompilerBridge
from runtime.context_builder import ExecutionContext

SETUPS = [{"id": "S001", "name": "LDN Bull", "requires": ["london", "bullish"]}]
SNAP   = {"symbol": "XAUUSD", "trend": "bullish", "session": "london",
           "atr": 5.0, "spread": 20.0, "market_status": "open",
           "timestamp": datetime(2026, 7, 30, 10, 0, 0, tzinfo=timezone.utc)}


def test_replay_1000x_stable():
    """1000 replay — no exception, no varied output."""
    bridge = CompilerBridge(SETUPS)
    actions = set()
    errors  = []
    for i in range(1000):
        try:
            ctx = ExecutionContext(market=SNAP)
            d = bridge.compile(ctx)
            actions.add(d.action)
        except Exception as e:
            errors.append(f"replay[{i}]: {e}")
    assert not errors, "Replay crashed:\n" + "\n".join(errors)
    assert len(actions) == 1, f"Non-deterministic output: {actions}"


def test_replay_100x_no_memory_growth():
    """Object count should stay stable across 100 replays."""
    bridge = CompilerBridge(SETUPS)
    gc.collect()
    before = len(gc.get_objects())
    for _ in range(100):
        ctx = ExecutionContext(market=SNAP)
        bridge.compile(ctx)
    gc.collect()
    after = len(gc.get_objects())
    growth = after - before
    # Allow 5% tolerance (100 * some overhead)
    assert growth < 500, f"Object count grew by {growth} — possible leak"
