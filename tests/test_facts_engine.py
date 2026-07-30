import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timezone, timedelta
from core.detectors.fact import Fact
from core.facts.fact_registry import FactRegistry
from core.facts.fact_validator import FactValidator
from core.facts.fact_resolver import FactResolver
from core.facts.facts_engine import FactsEngine
from core.facts.factset import FactSet


def make_fact(detector_id="d1", fact_type="trend", value="bullish", age_seconds=0):
    ts = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    return Fact(detector_id=detector_id, fact_type=fact_type, value=value, timestamp=ts)


# ── FactRegistry ────────────────────────────────────────────────────────────

def test_registry_add_and_list():
    r = FactRegistry()
    r.add(make_fact())
    assert len(r.list()) == 1

def test_registry_remove():
    r = FactRegistry()
    f = make_fact()
    r.add(f)
    r.remove(f)
    assert len(r) == 0

def test_registry_filter():
    r = FactRegistry()
    r.add(make_fact(fact_type="trend"))
    r.add(make_fact(fact_type="session"))
    result = r.filter(lambda f: f.fact_type == "trend")
    assert len(result) == 1

def test_registry_clear():
    r = FactRegistry()
    r.add(make_fact())
    r.clear()
    assert len(r) == 0


# ── FactValidator ───────────────────────────────────────────────────────────

def test_validator_removes_duplicate():
    v = FactValidator()
    facts = [make_fact(), make_fact()]  # same detector_id+type+value
    valid, issues = v.validate_all(facts)
    assert len(valid) == 1
    assert any("Duplicate" in i for i in issues)

def test_validator_removes_expired():
    v = FactValidator()
    old = make_fact(age_seconds=400)
    valid, issues = v.validate_all([old])
    assert len(valid) == 0
    assert any("Expired" in i for i in issues)

def test_validator_removes_invalid():
    v = FactValidator()
    bad = Fact(detector_id="d1", fact_type="", value=None)
    valid, issues = v.validate_all([bad])
    assert len(valid) == 0


# ── FactResolver ────────────────────────────────────────────────────────────

def test_resolver_detects_conflict():
    r = FactResolver()
    facts = [
        make_fact(detector_id="d1", fact_type="trend", value="bullish"),
        make_fact(detector_id="d2", fact_type="trend", value="bearish"),
    ]
    _, conflicts = r.resolve(facts)
    assert len(conflicts) == 1
    assert conflicts[0]["fact_type"] == "trend"

def test_resolver_no_conflict():
    r = FactResolver()
    facts = [make_fact(detector_id="d1", fact_type="trend", value="bullish")]
    _, conflicts = r.resolve(facts)
    assert len(conflicts) == 0


# ── FactsEngine ─────────────────────────────────────────────────────────────

def test_facts_engine_generates_factset():
    engine = FactsEngine()
    facts = [make_fact(detector_id="d1", fact_type="trend", value="bullish")]
    fs = engine.process(facts, market="XAUUSD", timeframe="M5")
    assert isinstance(fs, FactSet)
    assert len(fs.facts) == 1
    assert fs.market == "XAUUSD"

def test_facts_engine_deduplicates():
    engine = FactsEngine()
    facts = [make_fact(), make_fact()]
    fs = engine.process(facts)
    assert len(fs.facts) == 1

def test_facts_engine_flags_conflicts():
    engine = FactsEngine()
    facts = [
        make_fact(detector_id="d1", fact_type="trend", value="bullish"),
        make_fact(detector_id="d2", fact_type="trend", value="bearish"),
    ]
    fs = engine.process(facts)
    assert len(fs.conflicts) == 1

def test_factset_repr():
    fs = FactSet(market="XAUUSD", facts=[make_fact()])
    assert "XAUUSD" in repr(fs)
