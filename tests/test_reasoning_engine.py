"""Test Sprint 3.2 — Reasoning Engine."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.reasoning.reasoning_engine import ReasoningEngine
from core.reasoning.dependency_resolver import DependencyResolver

SNRC1 = {"id":"BYS-SETUP-003","name":"SNRC1","requires":["BYS-ST001","BYS-L001","BYS-CF007"]}
HYBRID1= {"id":"BYS-SETUP-001","name":"Hybrid 1","requires":["BYS-ST001","BYS-ST004","BYS-L019"]}
QMR   = {"id":"BYS-SETUP-006","name":"QMR","requires":["BYS-ST011","BYS-CF007","BYS-CF008"]}

@pytest.fixture
def engine(): return ReasoningEngine([SNRC1, HYBRID1, QMR])

def test_full_match(engine):
    facts = {"BYS-ST001","BYS-L001","BYS-CF007"}
    r = engine.reason(facts)
    snrc = next(c for c in r.candidates if c.setup_id=="BYS-SETUP-003")
    assert snrc.status == "MATCH" and snrc.score == 1.0

def test_partial(engine):
    r = engine.reason({"BYS-ST001","BYS-L001"})
    snrc = next(c for c in r.candidates if c.setup_id=="BYS-SETUP-003")
    assert snrc.status == "PARTIAL"

def test_no_match(engine):
    r = engine.reason({"some_random_fact"})
    for c in r.candidates: assert c.status == "NO_MATCH"

def test_missing_deps(engine):
    r = engine.reason({"BYS-ST001"})
    snrc = next(c for c in r.candidates if c.setup_id=="BYS-SETUP-003")
    assert "BYS-L001" in snrc.missing_dependencies

def test_multiple_candidates(engine):
    r = engine.reason({"BYS-ST001","BYS-ST004","BYS-L001","BYS-L019","BYS-CF007"})
    assert len(r.candidates) == 3

def test_ranking(engine):
    facts = {"BYS-ST001","BYS-L001","BYS-CF007","BYS-ST004","BYS-L019"}
    r = engine.reason(facts)
    scores = [c.score for c in r.candidates]
    assert scores == sorted(scores, reverse=True)

def test_no_buy_sell_in_result(engine):
    r = engine.reason({"BYS-ST001"})
    for c in r.candidates:
        assert "BUY" not in c.reason
        assert "SELL" not in c.reason

def test_optional_dep_resolver():
    dr = DependencyResolver()
    matched, missing = dr.resolve(["BYS-ST001","BYS-CF007"], {"BYS-ST001"})
    assert "BYS-ST001" in matched and "BYS-CF007" in missing
