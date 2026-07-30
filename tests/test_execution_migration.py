"""Test Sprint 5.7 — Execution Migration."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import MagicMock
from core.execution.execution_contract import ExecutionContract
from runtime.execution_runtime import ExecutionRuntime
from runtime.execution_result import ExecutionResult
from runtime.order_converter import OrderConverter
from runtime.execution_service import ExecutionService
from runtime.runtime_logger import RuntimeLogger
from adapters.broker.models import OrderResponse


def make_contract(**kwargs):
    defaults = dict(contract_id="t01", action="BUY", symbol="XAUUSD",
                    direction="BUY", entry=2000.0, sl=1990.0, tp=2020.0,
                    confidence=0.8, methodology="bystra",
                    setup="SNRC_1", entry_pattern="RBR",
                    metadata={"volume": 0.1})
    defaults.update(kwargs)
    return ExecutionContract(**defaults)


def mock_broker(status="FILLED", price=2000.0):
    b = MagicMock()
    b.submit_order.return_value = OrderResponse(
        order_id="ORD001", status=status,
        filled_price=price, filled_volume=0.1)
    return b


# ── OrderConverter ────────────────────────────────────────────────────────────
def test_converter_fields():
    c = make_contract()
    order = OrderConverter().convert(c)
    assert order.symbol == "XAUUSD"
    assert order.side == "BUY"
    assert order.volume == 0.1
    assert order.stop_loss == 1990.0
    assert order.take_profit == 2020.0
    assert "TIE:t01" in order.comment


def test_converter_no_trading_logic():
    # Converter MUST NOT recalculate SL/TP
    c = make_contract(sl=1995.0, tp=2030.0)
    order = OrderConverter().convert(c)
    assert order.stop_loss == 1995.0
    assert order.take_profit == 2030.0


def test_converter_metadata_passthrough():
    c = make_contract(metadata={"volume": 0.2, "be_trigger_atr": 1.5})
    order = OrderConverter().convert(c)
    assert order.metadata.get("be_trigger_atr") == 1.5


# ── ExecutionRuntime ──────────────────────────────────────────────────────────
def test_execute_buy():
    rt = ExecutionRuntime(broker_adapter=mock_broker())
    r = rt.execute(make_contract())
    assert r.success
    assert r.order_id == "ORD001"
    assert r.status == "FILLED"


def test_execute_wait_skipped():
    rt = ExecutionRuntime(broker_adapter=mock_broker())
    r = rt.execute(make_contract(action="WAIT", direction=""))
    assert not r.success
    assert r.status == "SKIPPED"


def test_execute_broker_reject():
    rt = ExecutionRuntime(broker_adapter=mock_broker(status="REJECTED"))
    r = rt.execute(make_contract())
    assert not r.success
    assert r.status == "REJECTED"


def test_execute_broker_exception():
    b = MagicMock()
    b.submit_order.side_effect = Exception("MT5 down")
    rt = ExecutionRuntime(broker_adapter=b)
    r = rt.execute(make_contract())
    assert not r.success
    assert r.status == "ERROR"
    assert "MT5 down" in r.error


# ── ExecutionService ──────────────────────────────────────────────────────────
def test_service_approve_and_execute():
    rt = ExecutionRuntime(broker_adapter=mock_broker())
    svc = ExecutionService(execution_runtime=rt)
    r = svc.submit(make_contract(), context={"spread": 50, "lot": 0.1})
    assert r.success


def test_service_risk_reject_blocks_broker():
    b = MagicMock()
    rt = ExecutionRuntime(broker_adapter=b)

    from core.rules.risk.spread_rule import SpreadRule
    from core.rules.plugins.plugin_registry import PluginRegistry
    reg = PluginRegistry()
    plugin = SpreadRule(); plugin.initialize({"max_spread": 10})
    reg.register("spread", plugin)

    svc = ExecutionService(execution_runtime=rt, risk_registry=reg)
    r = svc.submit(make_contract(), context={"spread": 500})
    assert not r.success
    assert r.status == "RISK_REJECTED"
    b.submit_order.assert_not_called()  # broker NOT called


# ── RuntimeLogger ─────────────────────────────────────────────────────────────
def test_logger_records():
    log = RuntimeLogger()
    log.log_contract_received("c01", "XAUUSD", "BUY")
    log.log_order_sent("c01", "ORD001")
    events = log.get_events("c01")
    assert len(events) == 2
    assert events[0]["event"] == "CONTRACT_RECEIVED"


def test_logger_no_imports_from_core_knowledge():
    import ast, pathlib
    src = pathlib.Path("runtime/execution_runtime.py").read_text()
    tree = ast.parse(src)
    banned = {"knowledge_loader", "pack_loader", "detector_engine",
              "setup_resolver", "decision_pipeline", "reasoning_engine"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = getattr(node, 'module', '') or ''
            for b in banned:
                assert b not in mod, f"execution_runtime imports banned: {b}"


# ── ExecutionResult ───────────────────────────────────────────────────────────
def test_result_repr():
    r = ExecutionResult(success=True, contract_id="c01", order_id="ORD1",
                        status="FILLED", filled_price=2001.5)
    assert "FILLED" in repr(r)


# ── Phase 3 frozen guard ──────────────────────────────────────────────────────
def test_phase3_frozen():
    from core.decision.decision_pipeline import DecisionPipeline
    assert DecisionPipeline
