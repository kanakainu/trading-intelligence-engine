import pytest, sys, os, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timezone
from core.detectors.fact import Fact
from core.facts.factset import FactSet
from core.setup.setup_result import SetupResult, SetupStatus
from core.decision.decision import Decision, Action
from core.decision.execution_plan import ExecutionPlan
from core.explanation.explanation_engine import ExplanationEngine
from core.explanation.explanation_builder import ExplanationBuilder
from core.explanation.explanation_registry import ExplanationRegistry
from core.explanation.explanation_validator import ExplanationValidator


def make_fact(t, v):
    return Fact(detector_id="d1", fact_type=t, value=v, timestamp=datetime.now(timezone.utc))

def make_factset():
    return FactSet(facts=[make_fact("trend","bullish"), make_fact("session","london")], market="XAUUSD")

def make_result(status=SetupStatus.PASS):
    return SetupResult(
        setup_id="S001", status=status, score=0.9, confidence=0.8,
        matched_rules=["trend eq bullish", "session eq london"],
        failed_rules=[], missing_facts=[]
    )

def make_decision(action=Action.BUY):
    plan = ExecutionPlan(entry_type="market", entry_zone=2000.0, stop_loss=1990.0, take_profit=2020.0)
    return Decision(
        decision_id="dec001", action=action, confidence=0.8,
        reason="Setup S001 PASS", setup_id="S001",
        execution_plan=plan if action != Action.WAIT else None
    )

@pytest.fixture
def engine():
    return ExplanationEngine()


def test_explanation_generated(engine):
    r = engine.explain(make_factset(), make_result(), make_decision())
    assert r.decision_id == "dec001"
    assert r.setup_id == "S001"
    assert "S001" in r.summary

def test_matched_facts(engine):
    r = engine.explain(make_factset(), make_result(), make_decision())
    assert len(r.matched_facts) == 2
    types = {f["fact_type"] for f in r.matched_facts}
    assert "trend" in types and "session" in types

def test_matched_rules(engine):
    r = engine.explain(make_factset(), make_result(), make_decision())
    assert len(r.matched_rules) == 2

def test_failed_rules_empty(engine):
    r = engine.explain(make_factset(), make_result(), make_decision())
    assert r.failed_rules == []

def test_confidence_breakdown(engine):
    r = engine.explain(make_factset(), make_result(), make_decision())
    assert "setup_score" in r.confidence_breakdown
    assert "decision_confidence" in r.confidence_breakdown

def test_execution_summary(engine):
    r = engine.explain(make_factset(), make_result(), make_decision())
    assert r.execution_summary["stop_loss"] == 1990.0
    assert r.execution_summary["take_profit"] == 2020.0

def test_json_export(engine):
    r = engine.explain(make_factset(), make_result(), make_decision())
    j = r.to_json()
    d = json.loads(j)
    assert d["decision_id"] == "dec001"
    assert "matched_facts" in d

def test_registry(engine):
    r = engine.explain(make_factset(), make_result(), make_decision())
    assert engine.registry.exists(r.report_id)

def test_validator_valid(engine):
    fs = make_factset()
    res = make_result()
    dec = make_decision()
    r = engine.explain(fs, res, dec)
    v = ExplanationValidator()
    ok, errs = v.validate(r, fs, res, dec)
    assert ok, errs

def test_validator_broken_decision_ref():
    v = ExplanationValidator()
    from core.explanation.explanation_report import ExplanationReport
    r = ExplanationReport(decision_id="WRONG", setup_id="S001")
    ok, errs = v.validate(r, make_factset(), make_result(), make_decision())
    assert not ok
    assert any("decision_id" in e for e in errs)

def test_audit_trail_integrity(engine):
    r = engine.explain(make_factset(), make_result(), make_decision())
    assert r.report_id
    assert r.timestamp
    assert r.decision_id == "dec001"
    assert r.setup_id == "S001"
    assert len(r.matched_facts) > 0
