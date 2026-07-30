"""Test Sprint 5.6 — Risk Migration (Rule Plugins)."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.rules.risk.confidence_rule import ConfidenceRule
from core.rules.risk.spread_rule import SpreadRule
from core.rules.risk.rr_rule import RRRule
from core.rules.risk.sl_tp_validation import SLValidationRule, TPValidationRule
from core.rules.risk.session_rule import SessionRule
from core.rules.risk.risk_registry import build_risk_registry


def init(cls, **cfg):
    p = cls(); p.initialize(cfg); return p


# ── SpreadRule ────────────────────────────────────────────────────────────────
def test_spread_approve():
    r = init(SpreadRule, max_spread=300).evaluate({"spread": 50}, {})
    assert r.status == "APPROVE"

def test_spread_reject():
    r = init(SpreadRule, max_spread=100).evaluate({"spread": 200}, {})
    assert r.status == "REJECT"


# ── ConfidenceRule ───────────────────────────────────────────────────────────
def test_conf_approve():
    r = init(ConfidenceRule, min_confidence=0.65).evaluate({}, {}, decision={"confidence": 0.8})
    assert r.status == "APPROVE"

def test_conf_reject():
    r = init(ConfidenceRule, min_confidence=0.65).evaluate({}, {}, decision={"confidence": 0.5})
    assert r.status == "REJECT"

def test_conf_bystra_normalise():
    # Bystra 7/10 → 0.7, should pass 0.65 threshold
    r = init(ConfidenceRule, min_confidence=0.65).evaluate({}, {}, decision={"confidence": 7.0})
    assert r.status == "APPROVE"

def test_conf_bystra_reject():
    r = init(ConfidenceRule, min_confidence=0.65).evaluate({}, {}, decision={"confidence": 5.0})
    assert r.status == "REJECT"


# ── RRRule ────────────────────────────────────────────────────────────────────
def test_rr_approve():
    ctx = {"entry": 2000.0, "sl": 1990.0, "tp": 2015.0, "direction": "BUY"}
    r = init(RRRule, min_rr=1.5).evaluate(ctx, {})
    assert r.status == "APPROVE"  # rr = 15/10 = 1.5

def test_rr_reject():
    ctx = {"entry": 2000.0, "sl": 1990.0, "tp": 2005.0, "direction": "BUY"}
    r = init(RRRule, min_rr=1.5).evaluate(ctx, {})
    assert r.status == "REJECT"  # rr = 5/10 = 0.5

def test_rr_no_sl():
    r = init(RRRule).evaluate({}, {})
    assert r.status == "APPROVE"  # skip if missing


# ── SL/TP Validation ──────────────────────────────────────────────────────────
def test_sl_valid_buy():
    r = init(SLValidationRule).evaluate({"entry": 2000.0, "sl": 1990.0, "direction": "BUY"}, {})
    assert r.status == "APPROVE"

def test_sl_invalid_buy():
    r = init(SLValidationRule).evaluate({"entry": 2000.0, "sl": 2010.0, "direction": "BUY"}, {})
    assert r.status == "REJECT"

def test_sl_valid_sell():
    r = init(SLValidationRule).evaluate({"entry": 2000.0, "sl": 2010.0, "direction": "SELL"}, {})
    assert r.status == "APPROVE"

def test_tp_valid_buy():
    r = init(TPValidationRule).evaluate({"entry": 2000.0, "tp": 2020.0, "direction": "BUY"}, {})
    assert r.status == "APPROVE"

def test_tp_invalid_sell():
    r = init(TPValidationRule).evaluate({"entry": 2000.0, "tp": 2020.0, "direction": "SELL"}, {})
    assert r.status == "REJECT"


# ── SessionRule ───────────────────────────────────────────────────────────────
def test_session_always_has_some_session():
    # At any UTC hour, some session window should be returned (ASIA covers 0-9)
    r = init(SessionRule, allowed_sessions=["ASIA", "LONDON", "NEW_YORK"]).evaluate({}, {})
    # Won't always approve (depends on time) but must not error
    assert r.status in ("APPROVE", "REJECT")


# ── Priority order ────────────────────────────────────────────────────────────
def test_priority_order():
    rules = [
        init(ConfidenceRule),
        init(SessionRule),
        init(SpreadRule),
        init(RRRule),
        init(SLValidationRule),
    ]
    priorities = [r.priority() for r in rules]
    assert priorities == sorted(priorities)


# ── risk_registry ─────────────────────────────────────────────────────────────
def test_build_risk_registry():
    reg = build_risk_registry()
    names = reg.list_all()
    assert "confidence" in names
    assert "spread" in names
    assert "rr" in names
    assert "sl_validation" in names
    assert "tp_validation" in names
    assert "news" in names
    assert "drawdown" in names
    assert "daily_target" in names
    assert "lot" in names

def test_registry_override():
    reg = build_risk_registry(overrides={"spread": {"max_spread": 50}})
    plugin = reg.get("spread")
    assert plugin._max_spread == 50
