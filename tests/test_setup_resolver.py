"""Test Sprint 3.5 — Setup Resolver (min 20 tests)."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.setup.setup_resolver import SetupResolver
from core.setup.setup_match import READY, PARTIAL, NOT_READY
from core.setup.setup_ranker import rank

SNRC1 = {"id":"BYS-SETUP-003","name":"SNRC1","confidence":0.8,
          "requires":["BYS-ST001","BYS-L001","BYS-CF007"]}
HYBRID1= {"id":"BYS-SETUP-001","name":"Hybrid 1","confidence":0.7,
           "requires":["BYS-ST001","BYS-ST004","BYS-L019"]}
QMR   = {"id":"BYS-SETUP-006","name":"QMR","confidence":0.65,
          "requires":["BYS-ST011","BYS-CF007","BYS-CF008"]}

@pytest.fixture
def resolver(): return SetupResolver([SNRC1, HYBRID1, QMR])

# ── READY ──────────────────────────────────────────────────────────────────
def test_snrc1_ready(resolver):
    r = resolver.resolve({"BYS-ST001","BYS-L001","BYS-CF007"}, set(), {})
    m = next(x for x in r if x.setup_id=="BYS-SETUP-003")
    assert m.status == READY and m.confidence == 0.8

def test_hybrid1_ready(resolver):
    r = resolver.resolve({"BYS-ST001","BYS-ST004","BYS-L019"}, set(), {})
    m = next(x for x in r if x.setup_id=="BYS-SETUP-001")
    assert m.status == READY

# ── PARTIAL ────────────────────────────────────────────────────────────────
def test_snrc1_partial(resolver):
    r = resolver.resolve({"BYS-ST001","BYS-L001"}, set(), {})
    m = next(x for x in r if x.setup_id=="BYS-SETUP-003")
    assert m.status == PARTIAL

def test_snrc1_partial_confidence_scaled(resolver):
    r = resolver.resolve({"BYS-ST001"}, set(), {})
    m = next(x for x in r if x.setup_id=="BYS-SETUP-003")
    assert m.confidence < 0.8

def test_waiting_for_populated(resolver):
    r = resolver.resolve({"BYS-ST001"}, set(), {})
    m = next(x for x in r if x.setup_id=="BYS-SETUP-003")
    assert "BYS-L001" in m.waiting_for

# ── NOT_READY ──────────────────────────────────────────────────────────────
def test_not_ready(resolver):
    r = resolver.resolve(set(), set(), {})
    for m in r: assert m.status == NOT_READY

def test_qmr_not_ready(resolver):
    r = resolver.resolve({"BYS-ST001"}, set(), {})
    m = next(x for x in r if x.setup_id=="BYS-SETUP-006")
    assert m.status == NOT_READY

# ── pattern_ids matching ───────────────────────────────────────────────────
def test_pattern_id_contributes(resolver):
    r = resolver.resolve({"BYS-L001","BYS-CF007"}, {"BYS-ST001"}, {})
    m = next(x for x in r if x.setup_id=="BYS-SETUP-003")
    assert m.status == READY

def test_context_facts_contribute(resolver):
    r = resolver.resolve({"BYS-L001","BYS-CF007"}, set(), {"BYS-ST001":"present"})
    m = next(x for x in r if x.setup_id=="BYS-SETUP-003")
    assert m.status == READY

# ── explanation & path ─────────────────────────────────────────────────────
def test_explanation_has_checkmark(resolver):
    r = resolver.resolve({"BYS-ST001","BYS-L001","BYS-CF007"}, set(), {})
    m = next(x for x in r if x.setup_id=="BYS-SETUP-003")
    assert "✓" in m.explanation

def test_explanation_has_fail_mark(resolver):
    r = resolver.resolve({"BYS-ST001"}, set(), {})
    m = next(x for x in r if x.setup_id=="BYS-SETUP-003")
    assert "✗" in m.explanation

def test_reasoning_path_populated(resolver):
    r = resolver.resolve({"BYS-ST001","BYS-L001","BYS-CF007"}, set(), {})
    m = next(x for x in r if x.setup_id=="BYS-SETUP-003")
    assert len(m.reasoning_path) == 3

# ── ranking ────────────────────────────────────────────────────────────────
def test_ranking_ready_first(resolver):
    r = resolver.resolve({"BYS-ST001","BYS-L001","BYS-CF007"}, set(), {})
    assert r[0].status == READY

def test_ranking_score_desc(resolver):
    r = resolver.resolve({"BYS-ST001","BYS-L001","BYS-CF007"}, set(), {})
    confs = [m.confidence for m in r]
    assert confs == sorted(confs, reverse=True)

def test_multiple_ready(resolver):
    r = resolver.resolve({"BYS-ST001","BYS-ST004","BYS-L019","BYS-L001","BYS-CF007"}, set(), {})
    ready = [m for m in r if m.status == READY]
    assert len(ready) >= 2

# ── no trading logic ────────────────────────────────────────────────────────
def test_no_buy_sell_in_explanation(resolver):
    r = resolver.resolve({"BYS-ST001","BYS-L001","BYS-CF007"}, set(), {})
    for m in r:
        assert "BUY" not in m.explanation
        assert "SELL" not in m.explanation

# ── ranker standalone ───────────────────────────────────────────────────────
def test_ranker_sorts_ready_first(resolver):
    r = resolver.resolve({"BYS-ST001"}, set(), {})
    ranked = rank(r)
    if any(m.status == READY for m in r):
        assert ranked[0].status == READY

# ── matched/missing ─────────────────────────────────────────────────────────
def test_matched_populated(resolver):
    r = resolver.resolve({"BYS-ST001","BYS-L001","BYS-CF007"}, set(), {})
    m = next(x for x in r if x.setup_id=="BYS-SETUP-003")
    assert len(m.matched_dependencies) == 3 and not m.missing_dependencies

def test_missing_populated(resolver):
    r = resolver.resolve({"BYS-ST001"}, set(), {})
    m = next(x for x in r if x.setup_id=="BYS-SETUP-003")
    assert len(m.missing_dependencies) == 2
