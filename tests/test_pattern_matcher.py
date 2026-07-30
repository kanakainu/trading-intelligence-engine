"""Test Sprint 3.4 — Pattern Matcher (min 18 tests)."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.patterns.pattern_definition import PatternDefinition
from core.patterns.pattern_match import MATCH, PARTIAL_MATCH, NO_MATCH
from core.patterns.pattern_matcher import PatternMatcher
from core.patterns.pattern_registry import PatternRegistry
from core.patterns.pattern_validator import PatternValidator
from core.rules.rule_result import RuleResult

def pass_rr(): return RuleResult(passed=True, matched=["ok"], trace=["PASS"])
def fail_rr(): return RuleResult(passed=False, failed=["x"], trace=["FAIL"])

RBR = PatternDefinition(id="RBR", name="Rally Base Rally", required_rules=["rally","base","rally2","bullish"])
@pytest.fixture
def matcher(): return PatternMatcher()

# ── MATCH ──────────────────────────────────────────────────────────────────
def test_full_match(matcher):
    rr = {"rally":pass_rr(),"base":pass_rr(),"rally2":pass_rr(),"bullish":pass_rr()}
    m = matcher.match(RBR, rr)
    assert m.status == MATCH and m.score == 1.0

# ── PARTIAL_MATCH ──────────────────────────────────────────────────────────
def test_partial_75(matcher):
    rr = {"rally":pass_rr(),"base":pass_rr(),"rally2":pass_rr(),"bullish":fail_rr()}
    m = matcher.match(RBR, rr)
    assert m.status == PARTIAL_MATCH and m.score == 0.75

def test_partial_50(matcher):
    rr = {"rally":pass_rr(),"base":pass_rr(),"rally2":fail_rr(),"bullish":fail_rr()}
    m = matcher.match(RBR, rr)
    assert m.status == PARTIAL_MATCH and m.score == 0.5

def test_partial_25(matcher):
    rr = {"rally":pass_rr(),"base":fail_rr(),"rally2":fail_rr(),"bullish":fail_rr()}
    m = matcher.match(RBR, rr)
    assert m.status == PARTIAL_MATCH and m.score == 0.25

# ── NO_MATCH ───────────────────────────────────────────────────────────────
def test_no_match_all_fail(matcher):
    rr = {"rally":fail_rr(),"base":fail_rr(),"rally2":fail_rr(),"bullish":fail_rr()}
    m = matcher.match(RBR, rr)
    assert m.status == NO_MATCH and m.score == 0.0

def test_no_match_empty(matcher):
    m = matcher.match(RBR, {})
    assert m.status == NO_MATCH

# ── matched/failed lists ───────────────────────────────────────────────────
def test_matched_populated(matcher):
    rr = {"rally":pass_rr(),"base":pass_rr(),"rally2":fail_rr(),"bullish":fail_rr()}
    m = matcher.match(RBR, rr)
    assert "rally" in m.matched_rules and "rally2" in m.failed_rules

def test_failed_populated(matcher):
    m = matcher.match(RBR, {})
    assert len(m.failed_rules) == 4

# ── explanation & trace ────────────────────────────────────────────────────
def test_explanation_has_checkmark(matcher):
    rr = {"rally":pass_rr(),"base":pass_rr(),"rally2":pass_rr(),"bullish":pass_rr()}
    m = matcher.match(RBR, rr)
    assert "✓" in m.explanation

def test_explanation_has_fail_mark(matcher):
    rr = {"rally":fail_rr(),"base":fail_rr(),"rally2":fail_rr(),"bullish":fail_rr()}
    m = matcher.match(RBR, rr)
    assert "✗" in m.explanation

def test_trace_populated(matcher):
    rr = {"rally":pass_rr(),"base":pass_rr(),"rally2":pass_rr(),"bullish":pass_rr()}
    m = matcher.match(RBR, rr)
    assert len(m.dependency_trace) == 4

# ── match_all ranking ──────────────────────────────────────────────────────
def test_match_all_ranked(matcher):
    p2 = PatternDefinition("P2","P2",["a","b"])
    p3 = PatternDefinition("P3","P3",["a"])
    rr = {"rally":pass_rr(),"base":pass_rr(),"rally2":pass_rr(),"bullish":pass_rr(),"a":pass_rr(),"b":fail_rr()}
    results = matcher.match_all([RBR,p2,p3], rr)
    assert results[0].status == MATCH

def test_match_all_descending_score(matcher):
    p2 = PatternDefinition("P2","P2",["a","b"])
    p3 = PatternDefinition("P3","P3",["a"])
    rr = {"rally":pass_rr(),"base":pass_rr(),"rally2":pass_rr(),"bullish":pass_rr(),"a":pass_rr(),"b":fail_rr()}
    results = matcher.match_all([p2,p3,RBR], rr)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)

# ── PatternRegistry ────────────────────────────────────────────────────────
def test_registry_register():
    r = PatternRegistry()
    r.register(RBR)
    assert r.exists("RBR") and r.get("RBR").name == "Rally Base Rally"

def test_registry_list():
    r = PatternRegistry()
    r.register(RBR)
    assert "RBR" in r.list()

def test_registry_all():
    r = PatternRegistry()
    r.register(RBR)
    assert len(r.all()) == 1

# ── PatternValidator ───────────────────────────────────────────────────────
def test_validator_valid():
    ok, e = PatternValidator().validate(RBR)
    assert ok

def test_validator_missing_id():
    ok, e = PatternValidator().validate(PatternDefinition("","X",["a"]))
    assert not ok

def test_validator_empty_rules():
    ok, e = PatternValidator().validate(PatternDefinition("P","X",[]))
    assert not ok
