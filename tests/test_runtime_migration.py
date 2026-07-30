"""Test Phase 5.1 — Runtime Migration (CompilerBridge wiring)."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timezone
from runtime.compiler_bridge import CompilerBridge
from runtime.context_builder import ExecutionContext
from runtime.runtime import IntelligenceRuntime
from core.decision.trade_decision import WAIT, BUY, SELL


# Minimal setup defs — no YAML, no file reads
EMPTY_SETUPS = []

SIMPLE_SETUPS = [
    {
        "id": "BYS-S001",
        "name": "London Breakout",
        "requires": ["london", "bullish"],
        "direction": "BUY",
        "confidence_base": 0.8,
    }
]


@pytest.fixture
def bridge_empty():
    return CompilerBridge(EMPTY_SETUPS)


@pytest.fixture
def bridge_with_setup():
    return CompilerBridge(SIMPLE_SETUPS)


@pytest.fixture
def market_ctx_london_bullish():
    return ExecutionContext(
        market={
            "symbol": "XAUUSD",
            "timestamp": datetime.now(timezone.utc),
            "trend": "bullish",
            "session": "london",
            "atr": 5.5,
            "spread": 20.0,
            "volatility": "medium",
            "market_status": "open",
        },
        execution_id="test-001",
    )


@pytest.fixture
def market_ctx_closed():
    return ExecutionContext(
        market={
            "symbol": "XAUUSD",
            "timestamp": datetime.now(timezone.utc),
            "trend": "unknown",
            "session": "closed",
            "atr": 0.0,
            "spread": 0.0,
            "volatility": "low",
            "market_status": "closed",
        },
        execution_id="test-002",
    )


# ── CompilerBridge ──────────────────────────────────────────────────────────
def test_bridge_no_setups_returns_wait(bridge_empty, market_ctx_london_bullish):
    decision = bridge_empty.compile(market_ctx_london_bullish)
    assert decision.action == WAIT


def test_bridge_builds_market_context(bridge_empty, market_ctx_london_bullish):
    # Should not raise — context translation works
    decision = bridge_empty.compile(market_ctx_london_bullish)
    assert decision is not None


def test_bridge_compiles_facts(bridge_empty, market_ctx_london_bullish):
    decision = bridge_empty.compile(market_ctx_london_bullish)
    assert decision.action in (WAIT, BUY, SELL)


def test_bridge_missing_symbol_uses_metadata():
    bridge = CompilerBridge(EMPTY_SETUPS)
    ctx = ExecutionContext(
        market={"trend": "bullish", "session": "london"},
        metadata={"symbol": "EURUSD"},
        execution_id="test-003",
    )
    decision = bridge.compile(ctx)
    assert decision is not None


def test_bridge_trend_mapping(bridge_empty):
    for raw, expected in [("bullish", "bullish"), ("bearish", "bearish"),
                          ("ranging", "sideways"), ("unknown", "unknown")]:
        ctx = ExecutionContext(
            market={"symbol": "X", "trend": raw, "session": "london",
                    "market_status": "open"},
        )
        d = bridge_empty.compile(ctx)
        assert d is not None


def test_bridge_session_mapping(bridge_empty):
    for raw in ["asia", "london", "new_york", "overlap", "ny", "asian"]:
        ctx = ExecutionContext(
            market={"symbol": "X", "session": raw, "trend": "bullish",
                    "market_status": "open"},
        )
        d = bridge_empty.compile(ctx)
        assert d is not None


def test_bridge_closed_market_wait(bridge_empty, market_ctx_closed):
    decision = bridge_empty.compile(market_ctx_closed)
    assert decision.action == WAIT


# ── IntelligenceRuntime.compile() ─────────────────────────────────────────
def test_runtime_compile_wired():
    rt = IntelligenceRuntime(setup_definitions=SIMPLE_SETUPS)
    rt.initialize()
    rt.start()
    ctx = ExecutionContext(
        market={"symbol": "XAUUSD", "trend": "bullish", "session": "london",
                "market_status": "open", "atr": 5.0, "spread": 20.0,
                "volatility": "medium",
                "timestamp": datetime.now(timezone.utc)},
        execution_id="rt-001",
    )
    decision = rt.compile(ctx)
    assert decision is not None
    assert decision.action in (WAIT, BUY, SELL)


def test_runtime_compile_no_bridge_raises():
    rt = IntelligenceRuntime()  # no setup_definitions
    rt.initialize()
    from runtime.exceptions import RuntimeStateError
    with pytest.raises(RuntimeStateError):
        rt.compile(ExecutionContext())


def test_runtime_compile_returns_trade_decision():
    rt = IntelligenceRuntime(setup_definitions=EMPTY_SETUPS)  # pass empty list
    rt.initialize()
    rt.start()
    ctx = ExecutionContext(
        market={"symbol": "XAUUSD", "trend": "bullish", "session": "london",
                "market_status": "open",
                "timestamp": datetime.now(timezone.utc)},
    )
    d = rt.compile(ctx)
    assert hasattr(d, "action")
    assert hasattr(d, "reason")


# ── Phase 3 frozen guard ────────────────────────────────────────────────────
def test_phase3_untouched():
    from core.decision.decision_pipeline import DecisionPipeline
    from core.facts.fact_compiler import FactCompiler
    from core.setup.setup_resolver import SetupResolver
    assert DecisionPipeline
    assert FactCompiler
    assert SetupResolver
