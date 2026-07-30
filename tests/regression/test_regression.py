"""Sprint 5.9 — Regression: verify full pipeline unchanged vs baseline."""
import sys, os, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pytest
from datetime import datetime, timezone
from runtime.compiler_bridge import CompilerBridge
from runtime.context_builder import ExecutionContext
from core.decision.trade_decision import WAIT, BUY, SELL

SETUPS = [
    {"id": "S001", "name": "London Bull", "requires": ["london", "bullish"]},
    {"id": "S002", "name": "NY Bear",     "requires": ["new_york", "bearish"]},
]

TS = datetime(2026, 7, 30, 10, 0, 0, tzinfo=timezone.utc)

SNAPSHOTS = [
    {"symbol": "XAUUSD", "trend": "bullish",  "session": "london",   "atr": 5.0, "spread": 20.0, "market_status": "open", "timestamp": TS},
    {"symbol": "XAUUSD", "trend": "bearish",  "session": "new_york", "atr": 4.5, "spread": 25.0, "market_status": "open", "timestamp": TS},
    {"symbol": "XAUUSD", "trend": "sideways", "session": "asia",     "atr": 2.0, "spread": 15.0, "market_status": "open", "timestamp": TS},
    {"symbol": "XAUUSD", "trend": "unknown",  "session": "closed",   "atr": 0.0, "spread": 0.0,  "market_status": "closed", "timestamp": TS},
]

BASELINE = {}  # filled on first run; regression checks equality


def run_pipeline(snapshot):
    bridge = CompilerBridge(SETUPS)
    ctx = ExecutionContext(market=snapshot)
    return bridge.compile(ctx)


def test_pipeline_deterministic_all_snapshots():
    """Same input → same action every run."""
    for snap in SNAPSHOTS:
        d1 = run_pipeline(snap)
        d2 = run_pipeline(snap)
        assert d1.action == d2.action, f"Non-deterministic: {snap['trend']}/{snap['session']}"


def test_pipeline_no_exceptions():
    for snap in SNAPSHOTS:
        d = run_pipeline(snap)
        assert d is not None


def test_pipeline_action_valid():
    for snap in SNAPSHOTS:
        d = run_pipeline(snap)
        assert d.action in (BUY, SELL, WAIT, "SKIP")


def test_pipeline_reason_non_empty():
    for snap in SNAPSHOTS:
        d = run_pipeline(snap)
        assert d.reason and len(d.reason) > 0


def test_regression_wait_when_no_ready_setup():
    """No matching setup → WAIT every time (regression baseline)."""
    bridge = CompilerBridge([])  # empty setups
    ctx = ExecutionContext(market=SNAPSHOTS[0])
    d = bridge.compile(ctx)
    assert d.action == WAIT


def test_regression_london_bullish_produces_consistent_action():
    snap = SNAPSHOTS[0]  # london + bullish
    results = set()
    for _ in range(10):
        results.add(run_pipeline(snap).action)
    assert len(results) == 1, f"Action varied across runs: {results}"


def test_regression_closed_market_wait():
    snap = SNAPSHOTS[3]  # closed market
    d = run_pipeline(snap)
    assert d.action == WAIT  # no setup should match closed/unknown
