"""Test Phase 4.0 — Compatibility Layer."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.compat.version import TIE_VERSION, PHASE4_VERSION, SUPPORTED_ADAPTER_TARGETS
from core.compat.adapter_interface import NullAdapter, AdapterInterface
from core.compat.migration_guard import MigrationGuard
from core.compat.compat_boundary import CompatBoundary
from core.execution.execution_contract import ExecutionContract, BUY

def make_contract():
    return ExecutionContract(action=BUY, symbol="XAUUSD", methodology="bystra",
                             setup="SNRC1", confidence=0.85)

# ── Version ────────────────────────────────────────────────────────────────
def test_versions_defined():
    assert TIE_VERSION and PHASE4_VERSION

def test_adapter_targets_frozen():
    assert "mt5" in SUPPORTED_ADAPTER_TARGETS
    assert "binance" in SUPPORTED_ADAPTER_TARGETS

# ── NullAdapter ────────────────────────────────────────────────────────────
def test_null_adapter_target():     assert NullAdapter().target == "null"
def test_null_adapter_noop():
    r = NullAdapter().send({"contract_id":"abc","action":BUY})
    assert r["status"] == "noop"

def test_adapter_interface_abstract():
    with pytest.raises(TypeError):
        AdapterInterface()

# ── MigrationGuard ─────────────────────────────────────────────────────────
def test_guard_register():
    MigrationGuard.register("4.0.0","TestModule")
    assert MigrationGuard._registered.get("TestModule") == "4.0.0"

def test_guard_assert_pass():
    MigrationGuard.register("4.0.0","GoodModule")
    MigrationGuard.assert_phase("4.0.0","GoodModule")

def test_guard_assert_fail():
    MigrationGuard.register("3.0.0","OldModule")
    with pytest.raises(RuntimeError):
        MigrationGuard.assert_phase("4.0.0","OldModule")

# ── CompatBoundary ─────────────────────────────────────────────────────────
def test_boundary_version_info():
    b = CompatBoundary()
    v = b.version_info()
    assert v["tie_version"] == TIE_VERSION and v["phase4_version"] == PHASE4_VERSION

def test_boundary_validate_target():
    b = CompatBoundary()
    assert b.validate_target("mt5")
    assert not b.validate_target("unknown_broker")

def test_boundary_forward_noop():
    b = CompatBoundary()
    r = b.forward(make_contract())
    assert r["status"] == "noop"

def test_boundary_dry_run_always_noop():
    custom = NullAdapter()
    b = CompatBoundary(adapter=custom)
    r = b.dry_run(make_contract())
    assert r["status"] == "noop"

def test_phase3_unchanged():
    """Verify core Phase 3 module imports still work after compat layer added."""
    from core.execution.execution_contract import ExecutionContract
    from core.decision.trade_decision import TradeDecision
    from core.execution.contract_builder import ContractBuilder
    assert ContractBuilder  # no import error
