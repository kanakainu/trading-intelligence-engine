import pytest, sys, os, uuid
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timezone
from core.setup.setup_result import SetupResult, SetupStatus
from core.decision.decision import Decision, Action
from core.decision.execution_plan import ExecutionPlan
from core.decision.decision_engine import DecisionEngine
from core.decision.decision_registry import DecisionRegistry
from core.decision.decision_validator import DecisionValidator


def make_result(status=SetupStatus.PASS, conf=0.8, direction="BUY",
                entry=2000.0, sl=1990.0, tp=2020.0):
    return SetupResult(
        setup_id="DUMMY",
        status=status,
        score=1.0,
        confidence=conf,
        metadata={
            "direction": direction,
            "entry_type": "market",
            "entry_zone": entry,
            "stop_loss": sl,
            "take_profit": tp,
            "risk_profile": "medium",
        }
    )


@pytest.fixture
def engine():
    return DecisionEngine()


# ── Action tests ──────────────────────────────────────────────────────────

def test_buy_decision(engine):
    d = engine.decide([make_result(direction="BUY")])[0]
    assert d.action == Action.BUY

def test_sell_decision(engine):
    d = engine.decide([make_result(direction="SELL", sl=2010.0, tp=1980.0)])[0]
    assert d.action == Action.SELL

def test_wait_on_fail(engine):
    d = engine.decide([make_result(status=SetupStatus.FAIL)])[0]
    assert d.action == Action.WAIT

def test_wait_on_low_confidence(engine):
    d = engine.decide([make_result(conf=0.3)])[0]
    assert d.action == Action.WAIT

def test_wait_no_direction(engine):
    d = engine.decide([make_result(direction="")])[0]
    assert d.action == Action.WAIT


# ── ExecutionPlan tests ───────────────────────────────────────────────────

def test_execution_plan_generated_for_buy(engine):
    d = engine.decide([make_result(direction="BUY")])[0]
    assert d.execution_plan is not None
    assert d.execution_plan.stop_loss == 1990.0
    assert d.execution_plan.take_profit == 2020.0

def test_execution_plan_none_for_wait(engine):
    d = engine.decide([make_result(status=SetupStatus.FAIL)])[0]
    assert d.execution_plan is None

def test_execution_plan_completeness():
    p = ExecutionPlan(entry_type="market", stop_loss=1990.0, take_profit=2020.0)
    assert p.is_complete()

def test_execution_plan_incomplete():
    p = ExecutionPlan(entry_type="market")
    assert not p.is_complete()


# ── DecisionRegistry ──────────────────────────────────────────────────────

def test_registry(engine):
    reg = DecisionRegistry()
    d = engine.decide([make_result()])[0]
    reg.register(d)
    assert reg.exists(d.decision_id)
    assert d.decision_id in reg.list()
    reg.unregister(d.decision_id)
    assert not reg.exists(d.decision_id)


# ── DecisionValidator ─────────────────────────────────────────────────────

def test_validator_valid(engine):
    d = engine.decide([make_result()])[0]
    v = DecisionValidator()
    ok, errs = v.validate(d)
    assert ok, errs

def test_validator_missing_plan():
    d = Decision(
        decision_id="X", action=Action.BUY, confidence=0.8,
        reason="test", setup_id="S1", execution_plan=None
    )
    v = DecisionValidator()
    ok, errs = v.validate(d)
    assert not ok
    assert "missing:execution_plan" in errs

def test_validator_invalid_confidence():
    d = Decision(
        decision_id="X", action=Action.WAIT, confidence=2.0,
        reason="test", setup_id="S1"
    )
    v = DecisionValidator()
    ok, errs = v.validate(d)
    assert not ok
    assert any("confidence" in e for e in errs)

def test_no_mt5_or_broker_import():
    import ast, inspect, core.decision.decision_engine as de
    src = inspect.getsource(de)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Name, ast.Attribute)):
            name = node.id if isinstance(node, ast.Name) else node.attr
            for f in ["mt5", "broker", "socket", "requests"]:
                assert f not in name.lower(), f"broker/network code in AST: {f}"
