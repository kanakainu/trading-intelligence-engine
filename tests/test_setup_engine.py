import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timezone
from core.detectors.fact import Fact
from core.facts.factset import FactSet
from core.setup.setup_engine import SetupEngine
from core.setup.setup_registry import SetupRegistry
from core.setup.setup_result import SetupStatus
from core.setup.rule_evaluator import evaluate_rule, _build_index
from core.setup.setup_validator import SetupValidator


def make_fact(t, v, d="det"):
    return Fact(detector_id=d, fact_type=t, value=v, timestamp=datetime.now(timezone.utc))

def make_factset(*pairs):
    facts = [make_fact(t, v) for t, v in pairs]
    return FactSet(facts=facts, market="TEST", timeframe="M5")

DUMMY_SETUP = {
    "id": "DUMMY_LONG",
    "name": "Dummy Long Setup",
    "confidence": 0.8,
    "rules": {
        "op": "AND",
        "rules": [
            {"fact": "trend",    "op": "eq",  "value": "bullish"},
            {"fact": "session",  "op": "eq",  "value": "london"},
            {"fact": "risk",     "op": "neq", "value": "HIGH"},
        ]
    }
}

@pytest.fixture
def registry():
    r = SetupRegistry()
    r.register(DUMMY_SETUP)
    return r

@pytest.fixture
def engine(registry):
    return SetupEngine(registry)


# ── RuleEvaluator ─────────────────────────────────────────────────────────

def test_and_pass():
    idx = {"trend": "bullish", "session": "london"}
    rule = {"op": "AND", "rules": [
        {"fact": "trend", "op": "eq", "value": "bullish"},
        {"fact": "session", "op": "eq", "value": "london"},
    ]}
    ok, _, m, f = evaluate_rule(rule, idx)
    assert ok and len(m) == 2 and len(f) == 0

def test_and_fail():
    idx = {"trend": "bearish"}
    rule = {"op": "AND", "rules": [
        {"fact": "trend", "op": "eq", "value": "bullish"},
    ]}
    ok, _, _, f = evaluate_rule(rule, idx)
    assert not ok

def test_or_pass():
    idx = {"trend": "bearish"}
    rule = {"op": "OR", "rules": [
        {"fact": "trend", "op": "eq", "value": "bullish"},
        {"fact": "trend", "op": "eq", "value": "bearish"},
    ]}
    ok, _, m, _ = evaluate_rule(rule, idx)
    assert ok and len(m) == 1

def test_or_fail():
    idx = {"trend": "sideways"}
    rule = {"op": "OR", "rules": [
        {"fact": "trend", "op": "eq", "value": "bullish"},
        {"fact": "trend", "op": "eq", "value": "bearish"},
    ]}
    ok, _, _, _ = evaluate_rule(rule, idx)
    assert not ok

def test_not():
    idx = {"risk": "LOW"}
    rule = {"op": "NOT", "rules": [{"fact": "risk", "op": "eq", "value": "HIGH"}]}
    ok, _, _, _ = evaluate_rule(rule, idx)
    assert ok

def test_nested():
    idx = {"trend": "bullish", "session": "london", "risk": "LOW"}
    rule = {"op": "AND", "rules": [
        {"fact": "trend", "op": "eq", "value": "bullish"},
        {"op": "OR", "rules": [
            {"fact": "session", "op": "eq", "value": "london"},
            {"fact": "session", "op": "eq", "value": "new_york"},
        ]},
        {"op": "NOT", "rules": [{"fact": "risk", "op": "eq", "value": "HIGH"}]},
    ]}
    ok, _, m, f = evaluate_rule(rule, idx)
    assert ok and len(f) == 0

def test_missing_fact():
    idx = {}
    rule = {"fact": "trend", "op": "eq", "value": "bullish"}
    ok, _, _, f = evaluate_rule(rule, idx)
    assert not ok and any("missing" in x for x in f)


# ── SetupRegistry ─────────────────────────────────────────────────────────

def test_registry_register_exists(registry):
    assert registry.exists("DUMMY_LONG")

def test_registry_list(registry):
    assert "DUMMY_LONG" in registry.list()

def test_registry_unregister(registry):
    registry.unregister("DUMMY_LONG")
    assert not registry.exists("DUMMY_LONG")


# ── SetupValidator ────────────────────────────────────────────────────────

def test_validator_valid():
    v = SetupValidator()
    ok, errs = v.validate(DUMMY_SETUP)
    assert ok, errs

def test_validator_missing_field():
    v = SetupValidator()
    ok, errs = v.validate({"id": "X", "name": "Y"})
    assert not ok and "missing_field:rules" in errs


# ── SetupEngine E2E ───────────────────────────────────────────────────────

def test_setup_engine_pass(engine):
    fs = make_factset(("trend", "bullish"), ("session", "london"), ("risk", "LOW"))
    results = engine.evaluate(fs)
    assert results[0].status == SetupStatus.PASS

def test_setup_engine_fail(engine):
    fs = make_factset(("trend", "bearish"), ("session", "london"), ("risk", "LOW"))
    results = engine.evaluate(fs)
    assert results[0].status == SetupStatus.FAIL

def test_setup_engine_missing_fact(engine):
    fs = make_factset(("trend", "bullish"))  # missing session, risk
    results = engine.evaluate(fs)
    assert results[0].status == SetupStatus.FAIL
    assert len(results[0].missing_facts) > 0

def test_setup_engine_no_yaml_import():
    import inspect, core.setup.setup_engine as se
    src = inspect.getsource(se)
    assert "import yaml" not in src
    assert "open(" not in src
