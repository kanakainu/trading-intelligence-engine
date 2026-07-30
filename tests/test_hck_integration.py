"""Test Sprint 6.2 — HCK Pipeline Integration."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from runtime.compiler_bridge import CompilerBridge
from runtime.execution_service import ExecutionService
from runtime.execution_runtime import ExecutionRuntime
from runtime.context_builder import ExecutionContext
from adapters.broker.models import OrderResponse
from core.execution.execution_contract import ExecutionContract


def mock_hck(episodes=None, semantic=None, goals=None):
    h = MagicMock()
    h.get_recent_episodes.return_value = episodes or [{"role": "user", "content": "buy XAUUSD"}]
    h.get_semantic_memory.return_value = semantic or [{"category": "fact", "content": "trend bullish"}]
    h.get_goals.return_value = goals or []
    h.write_episode.return_value = True
    h.publish_event.return_value = True
    return h


SETUPS = [{"id": "S001", "name": "LDN Bull", "requires": ["london", "bullish"]}]
TS = datetime(2026, 7, 30, 10, 0, 0, tzinfo=timezone.utc)
SNAP = {"symbol": "XAUUSD", "trend": "bullish", "session": "london",
        "market_status": "open", "timestamp": TS}


# ── Point 1: CompilerBridge HCK inject ────────────────────────────────────
def test_compiler_bridge_injects_hck_memory():
    hck = mock_hck()
    bridge = CompilerBridge(SETUPS, hck_bridge=hck)
    ctx = ExecutionContext(market=SNAP, metadata={"canonical_id": "boskuh_id"})
    bridge.compile(ctx)
    assert "hck_episodes" in ctx.memory
    assert "hck_semantic" in ctx.memory
    hck.get_recent_episodes.assert_called_once_with("boskuh_id", limit=5)
    hck.get_semantic_memory.assert_called_once_with("boskuh_id", limit=10)

def test_compiler_bridge_no_hck_still_works():
    bridge = CompilerBridge(SETUPS)  # no hck
    ctx = ExecutionContext(market=SNAP)
    d = bridge.compile(ctx)
    assert d is not None
    assert "hck_episodes" not in ctx.memory

def test_compiler_bridge_hck_fail_nonfatal():
    hck = MagicMock()
    hck.get_recent_episodes.side_effect = Exception("HCK down")
    bridge = CompilerBridge(SETUPS, hck_bridge=hck)
    ctx = ExecutionContext(market=SNAP, metadata={"canonical_id": "x"})
    d = bridge.compile(ctx)  # must not crash
    assert d is not None


# ── Point 2: ExecutionService write episode ────────────────────────────────
def test_execution_service_writes_episode_on_fill():
    hck = mock_hck()
    broker = MagicMock()
    broker.submit_order.return_value = OrderResponse(
        order_id="ORD1", status="FILLED",
        filled_price=2001.0, filled_volume=0.1)
    rt = ExecutionRuntime(broker_adapter=broker)
    svc = ExecutionService(execution_runtime=rt, hck_bridge=hck)
    contract = ExecutionContract(symbol="XAUUSD", direction="BUY", action="BUY",
                                 entry=2000.0, sl=1990.0, tp=2020.0,
                                 confidence=0.8, setup="SNRC_1",
                                 methodology="bystra", entry_pattern="RBR",
                                 metadata={"canonical_id": "boskuh_id", "volume": 0.1})
    r = svc.submit(contract, context={"canonical_id": "boskuh_id"})
    assert r.success
    hck.write_episode.assert_called_once()
    hck.publish_event.assert_called_once_with("TRADE_EXECUTED", pytest.approx(
        {"canonical_id": "boskuh_id", "contract_id": contract.contract_id,
         "symbol": "XAUUSD", "direction": "BUY", "filled_price": 2001.0},
        abs=1))

def test_execution_service_no_write_on_reject():
    hck = mock_hck()
    broker = MagicMock()
    broker.submit_order.return_value = OrderResponse(
        order_id="ORD2", status="REJECTED", error="Margin insufficient")
    rt = ExecutionRuntime(broker_adapter=broker)
    svc = ExecutionService(execution_runtime=rt, hck_bridge=hck)
    contract = ExecutionContract(symbol="XAUUSD", direction="BUY", action="BUY",
                                 entry=2000.0, metadata={"volume": 0.1})
    svc.submit(contract, context={})
    hck.write_episode.assert_not_called()


# ── Point 3: ExecutionService inject HCK goals ────────────────────────────
def test_execution_service_injects_goals_into_context():
    hck = mock_hck(goals=[{"category": "goal", "content": "daily_target: $30"}])
    broker = MagicMock()
    broker.submit_order.return_value = OrderResponse(status="FILLED", filled_price=2000.0)
    rt = ExecutionRuntime(broker_adapter=broker)

    captured_ctx = {}
    from core.rules.plugins.plugin_interface import RuleResult
    from core.rules.plugins.plugin_registry import PluginRegistry
    from core.rules.plugins.plugin_interface import RulePluginInterface

    class CaptureDailyPlugin(RulePluginInterface):
        def initialize(self, cfg): pass
        def evaluate(self, ctx, *a, **kw):
            captured_ctx.update(ctx)
            return RuleResult("APPROVE", "ok")
        def metadata(self): return {}
        def priority(self): return 1
        def enabled(self): return True

    reg = PluginRegistry()
    reg.register("capture", CaptureDailyPlugin())
    svc = ExecutionService(execution_runtime=rt, risk_registry=reg, hck_bridge=hck)
    contract = ExecutionContract(symbol="XAUUSD", direction="BUY", action="BUY",
                                 entry=2000.0, metadata={"canonical_id": "boskuh_id", "volume": 0.1})
    svc.submit(contract, context={"canonical_id": "boskuh_id"})
    assert "hck_goals" in captured_ctx


# ── HCK fail in ExecutionService nonfatal ─────────────────────────────────
def test_execution_service_hck_fail_nonfatal():
    hck = MagicMock()
    hck.get_goals.side_effect = Exception("HCK down")
    hck.write_episode.side_effect = Exception("HCK down")
    broker = MagicMock()
    broker.submit_order.return_value = OrderResponse(
        order_id="ORD", status="FILLED", filled_price=2000.0, filled_volume=0.1)
    rt = ExecutionRuntime(broker_adapter=broker)
    svc = ExecutionService(execution_runtime=rt, hck_bridge=hck)
    contract = ExecutionContract(symbol="X", direction="BUY", action="BUY",
                                 entry=2000.0, metadata={"volume": 0.1})
    r = svc.submit(contract, context={"canonical_id": "x"})
    assert r.success  # must not crash
