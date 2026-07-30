"""Test Phase 4.0 — Compatibility Layer + Phase 4.1 compat tests."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.compatibility import (
    CURRENT_VERSION, TARGET_VERSION, current, target, compatible,
    contract_to_dict, dict_to_contract_stub,
    check_contract, backward_compatible, migration_ready, check
)
from core.execution.execution_contract import ExecutionContract, BUY

def valid_contract():
    c = ExecutionContract(action=BUY, symbol="XAUUSD", confidence=0.85)
    return contract_to_dict(c)

# ── version ──────────────────────────────────────────────────────────────
def test_versions_defined():        assert CURRENT_VERSION and TARGET_VERSION
def test_parse_current():           assert str(current()) == CURRENT_VERSION
def test_parse_target():            assert str(target()) == TARGET_VERSION
def test_major_mismatch():          assert not compatible("3.0.0","4.0.0")
def test_minor_compat():            assert compatible("3.0.0","3.9.9")

# ── schema mapper ─────────────────────────────────────────────────────────
def test_contract_to_dict():
    d = valid_contract()
    assert "action" in d and d["action"] == BUY

def test_dict_to_stub():
    d = valid_contract()
    stub = dict_to_contract_stub(d)
    assert stub["action"] == BUY and stub["_source"] == "phase3"

def test_roundtrip_action():
    d = valid_contract()
    stub = dict_to_contract_stub(d)
    assert stub["action"] == d["action"]

# ── migration guard ───────────────────────────────────────────────────────
def test_valid_guard():
    ok, e = check_contract(valid_contract())
    assert ok, e

def test_invalid_action_guard():
    d = valid_contract(); d["action"] = "FIRE"
    ok, e = check_contract(d)
    assert not ok

def test_missing_field_guard():
    d = valid_contract(); del d["action"]
    ok, e = check_contract(d)
    assert not ok

def test_backward_compat():         assert backward_compatible(valid_contract())

def test_migration_ready():
    ok, warnings = migration_ready(valid_contract())
    assert ok

# ── compatibility checker ─────────────────────────────────────────────────
def test_check_no_contract():
    r = check()
    assert r["migration_ready"] is True

def test_check_with_valid():
    r = check(valid_contract())
    assert r["migration_ready"] is True
    assert not r["errors"]

def test_check_with_invalid():
    d = valid_contract(); d["action"] = "INVALID"
    r = check(d)
    assert r["phase3_status"] == "invalid_contract"

def test_phase3_frozen():
    """Phase 3 imports work unchanged after compat layer."""
    from core.execution.execution_contract import ExecutionContract
    from core.decision.trade_decision import TradeDecision
    from core.execution.contract_builder import ContractBuilder
    assert ContractBuilder
