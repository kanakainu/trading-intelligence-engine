"""Test Sprint 3.3 — Rule Engine."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.rules.rule import AtomicRule, CompoundRule
from core.rules.operator import Op
from core.rules.rule_engine import RuleEngine

@pytest.fixture
def eng(): return RuleEngine()

def a(fact, op, val=None): return AtomicRule(fact=fact, op=op, value=val)

# ── atomic ops ─────────────────────────────────────────────────────────────
def test_eq_pass(eng):   assert eng.evaluate(a("trend",Op.EQ,"bullish"), {"trend":"bullish"}).passed
def test_eq_fail(eng):   assert not eng.evaluate(a("trend",Op.EQ,"bullish"), {"trend":"bearish"}).passed
def test_neq(eng):       assert eng.evaluate(a("trend",Op.NEQ,"bearish"), {"trend":"bullish"}).passed
def test_gt(eng):        assert eng.evaluate(a("atr",Op.GT,100), {"atr":150}).passed
def test_gte(eng):       assert eng.evaluate(a("atr",Op.GTE,150), {"atr":150}).passed
def test_lt(eng):        assert eng.evaluate(a("atr",Op.LT,200), {"atr":150}).passed
def test_lte(eng):       assert eng.evaluate(a("atr",Op.LTE,150), {"atr":150}).passed
def test_in(eng):        assert eng.evaluate(a("session",Op.IN,["london","new_york"]), {"session":"london"}).passed
def test_not_in(eng):    assert eng.evaluate(a("session",Op.NOT_IN,["asia"]), {"session":"london"}).passed
def test_exists(eng):    assert eng.evaluate(a("trend",Op.EXISTS), {"trend":"bullish"}).passed
def test_not_exists(eng):assert eng.evaluate(a("danger",Op.NOT_EXISTS), {"trend":"bullish"}).passed
def test_between(eng):   assert eng.evaluate(a("atr",Op.BETWEEN,[100,200]), {"atr":150}).passed
def test_between_fail(eng): assert not eng.evaluate(a("atr",Op.BETWEEN,[100,140]), {"atr":150}).passed

# ── compound ───────────────────────────────────────────────────────────────
def test_and_pass(eng):
    r = CompoundRule("AND",[a("trend",Op.EQ,"bullish"),a("session",Op.EQ,"london")])
    assert eng.evaluate(r, {"trend":"bullish","session":"london"}).passed

def test_and_fail(eng):
    r = CompoundRule("AND",[a("trend",Op.EQ,"bullish"),a("session",Op.EQ,"asia")])
    assert not eng.evaluate(r, {"trend":"bullish","session":"london"}).passed

def test_or_pass(eng):
    r = CompoundRule("OR",[a("trend",Op.EQ,"bearish"),a("trend",Op.EQ,"bullish")])
    assert eng.evaluate(r, {"trend":"bullish"}).passed

def test_or_fail(eng):
    r = CompoundRule("OR",[a("trend",Op.EQ,"bearish"),a("session",Op.EQ,"asia")])
    assert not eng.evaluate(r, {"trend":"bullish","session":"london"}).passed

def test_not(eng):
    r = CompoundRule("NOT",[a("danger",Op.EXISTS)])
    assert eng.evaluate(r, {"trend":"bullish"}).passed

def test_nested(eng):
    r = CompoundRule("AND",[
        a("trend",Op.EQ,"bullish"),
        CompoundRule("OR",[a("session",Op.EQ,"london"),a("session",Op.EQ,"new_york")]),
        CompoundRule("NOT",[a("danger",Op.EXISTS)]),
    ])
    assert eng.evaluate(r, {"trend":"bullish","session":"london"}).passed

# ── result fields ──────────────────────────────────────────────────────────
def test_matched_facts(eng):
    r = eng.evaluate(a("trend",Op.EQ,"bullish"), {"trend":"bullish"})
    assert r.matched and not r.failed

def test_failed_facts(eng):
    r = eng.evaluate(a("trend",Op.EQ,"bullish"), {"trend":"bearish"})
    assert r.failed and not r.matched

def test_explanation_contains_pass_mark(eng):
    r = eng.evaluate(a("trend",Op.EQ,"bullish"), {"trend":"bullish"})
    assert "✓" in r.explanation

def test_trace_populated(eng):
    r = eng.evaluate(a("trend",Op.EQ,"bullish"), {"trend":"bullish"})
    assert r.trace
