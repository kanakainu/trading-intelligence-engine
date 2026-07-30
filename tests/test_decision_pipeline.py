"""Test Sprint 3.6 — Decision Pipeline (min 20 tests)."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.setup.setup_match import SetupMatch, READY, PARTIAL, NOT_READY
from core.decision.decision_pipeline import DecisionPipeline
from core.decision.decision_policy import DecisionPolicy
from core.decision.trade_decision import BUY, SELL, WAIT, SKIP

def sm(id, name, status=READY, conf=0.8, matched=None, missing=None):
    return SetupMatch(setup_id=id, setup_name=name, status=status,
                      confidence=conf, matched_dependencies=matched or [],
                      missing_dependencies=missing or [])

@pytest.fixture
def pipe(): return DecisionPipeline()

SNRC1  = sm("BYS-SETUP-003","SNRC1", READY, 0.85, ["BYS-ST001","BYS-L001"])
HYBRID = sm("BYS-SETUP-001","Hybrid 1", READY, 0.75, ["BYS-ST001","BYS-ST004"])
QMR    = sm("BYS-SETUP-006","QMR", PARTIAL, 0.45, ["BYS-ST011"], ["BYS-CF007"])
LOW    = sm("BYS-SETUP-010","Blindspot", READY, 0.50, ["BYS-C025"])

# ── BUY/SELL/WAIT/SKIP ─────────────────────────────────────────────────────
def test_buy_when_ready(pipe):
    d = pipe.decide([SNRC1])
    assert d.action == BUY

def test_wait_no_ready(pipe):
    d = pipe.decide([QMR])
    assert d.action == WAIT

def test_wait_empty(pipe):
    assert pipe.decide([]).action == WAIT

def test_wait_below_threshold(pipe):
    policy = DecisionPolicy(min_confidence=0.80)
    d = DecisionPipeline(policy).decide([LOW])
    assert d.action == WAIT

def test_skip(pipe):
    d = pipe.skip("manual")
    assert d.action == SKIP

def test_multiple_ready_picks_best(pipe):
    d = pipe.decide([HYBRID, SNRC1])
    assert d.setup_id == "BYS-SETUP-003"  # SNRC1 higher conf

def test_confidence_set(pipe):
    d = pipe.decide([SNRC1])
    assert d.confidence == 0.85

def test_setup_id_set(pipe):
    d = pipe.decide([SNRC1])
    assert d.setup_id == "BYS-SETUP-003"

def test_setup_name_set(pipe):
    d = pipe.decide([SNRC1])
    assert d.setup_name == "SNRC1"

# ── ranking ────────────────────────────────────────────────────────────────
def test_ranking_populated(pipe):
    d = pipe.decide([SNRC1, HYBRID, QMR])
    assert len(d.ranking) == 3

def test_ranking_ready_before_partial(pipe):
    d = pipe.decide([QMR, SNRC1])
    assert d.ranking[0]["status"] == READY

# ── reason & trace ─────────────────────────────────────────────────────────
def test_reason_set(pipe):
    d = pipe.decide([SNRC1])
    assert d.reason

def test_trace_populated(pipe):
    d = pipe.decide([SNRC1])
    assert d.trace

def test_wait_reason_set(pipe):
    d = pipe.decide([])
    assert d.reason

# ── no trading logic ────────────────────────────────────────────────────────
def test_no_lot_size(pipe):
    d = pipe.decide([SNRC1])
    assert not hasattr(d, "lot_size")

def test_no_sl_tp(pipe):
    d = pipe.decide([SNRC1])
    assert not hasattr(d, "stop_loss")
    assert not hasattr(d, "take_profit")

def test_no_broker(pipe):
    d = pipe.decide([SNRC1])
    assert not hasattr(d, "broker")

def test_no_mt5(pipe):
    d = pipe.decide([SNRC1])
    assert not hasattr(d, "mt5")

# ── policy ─────────────────────────────────────────────────────────────────
def test_custom_min_confidence(pipe):
    policy = DecisionPolicy(min_confidence=0.90)
    d = DecisionPipeline(policy).decide([SNRC1])
    assert d.action == WAIT  # 0.85 < 0.90

def test_custom_policy_pass(pipe):
    policy = DecisionPolicy(min_confidence=0.70)
    d = DecisionPipeline(policy).decide([SNRC1])
    assert d.action == BUY   # 0.85 >= 0.70
