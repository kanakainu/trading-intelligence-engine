"""Test Sprint 3.8 — Execution Contract (min 15 tests)."""
import pytest, sys, os, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.execution.execution_contract import ExecutionContract, BUY, SELL, WAIT, SKIP
from core.execution.contract_builder import ContractBuilder
from core.execution.contract_validator import ContractValidator
from core.execution.contract_serializer import to_dict, to_json
from core.decision.trade_decision import TradeDecision

def make_decision(action=BUY, setup="SNRC1", sid="BYS-003", conf=0.85):
    return TradeDecision(action=action, setup_id=sid, setup_name=setup,
                         confidence=conf, reason=f"High conf: {setup} {conf:.0%}")

@pytest.fixture
def builder(): return ContractBuilder()
@pytest.fixture
def contract(builder): return builder.build(make_decision(), symbol="XAUUSD", methodology="bystra")

# ── Build ──────────────────────────────────────────────────────────────────
def test_build_returns_contract(contract):
    assert isinstance(contract, ExecutionContract)

def test_action_set(contract):   assert contract.action == BUY
def test_symbol_set(contract):   assert contract.symbol == "XAUUSD"
def test_method_set(contract):   assert contract.methodology == "bystra"
def test_setup_set(contract):    assert contract.setup == "SNRC1"
def test_confidence_set(contract): assert contract.confidence == 0.85
def test_contract_id_set(contract): assert contract.contract_id
def test_timestamp_set(contract): assert contract.timestamp

# ── Validator ──────────────────────────────────────────────────────────────
def test_valid_contract(contract):
    ok, e = ContractValidator().validate(contract)
    assert ok, e

def test_invalid_action():
    c = ExecutionContract(action="FIRE", confidence=0.8)
    ok, e = ContractValidator().validate(c)
    assert not ok

def test_invalid_confidence():
    c = ExecutionContract(action=BUY, confidence=2.0)
    ok, e = ContractValidator().validate(c)
    assert not ok

# ── Serializer ─────────────────────────────────────────────────────────────
def test_to_dict(contract):
    d = to_dict(contract)
    assert isinstance(d, dict) and "action" in d and "symbol" in d

def test_to_json(contract):
    j = to_json(contract)
    d = json.loads(j)
    assert d["action"] == BUY and d["symbol"] == "XAUUSD"

def test_no_lot_margin_in_contract(contract):
    d = to_dict(contract)
    assert "lot" not in d and "margin" not in d and "broker" not in d

def test_all_actions(builder):
    for action in [BUY, SELL, WAIT, SKIP]:
        d = make_decision(action=action)
        c = builder.build(d, symbol="XAUUSD")
        ok, _ = ContractValidator().validate(c)
        assert ok
