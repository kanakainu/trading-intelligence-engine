"""Test Sprint 3.7 — Explanation Generator (min 18 tests)."""
import pytest, sys, os, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.explanation.explanation_generator import ExplanationGenerator
from core.explanation.explanation_report import ExplanationReport
from core.explanation.markdown_renderer import render_markdown
from core.explanation.json_renderer import render_json, render_dict
from core.explanation.trace_tree import build_trace_tree
from core.facts.typed_facts import TrendFact, SessionFact
from core.setup.setup_match import SetupMatch, READY
from core.decision.trade_decision import TradeDecision, BUY, WAIT

def make_fact(name, value, t="TrendFact"):
    f = TrendFact(value=value) if name=="trend" else SessionFact(value=value)
    return f

def make_setup():
    return SetupMatch(setup_id="BYS-SETUP-003", setup_name="SNRC1",
                      status=READY, confidence=0.85,
                      matched_dependencies=["BYS-ST001","BYS-L001"],
                      missing_dependencies=[])

def make_decision():
    return TradeDecision(action=BUY, setup_id="BYS-SETUP-003",
                         setup_name="SNRC1", confidence=0.85,
                         reason="Highest confidence: SNRC1 85%")

@pytest.fixture
def gen(): return ExplanationGenerator()
@pytest.fixture
def report(gen):
    facts = [make_fact("trend","bullish"), make_fact("session","london")]
    return gen.generate(facts=facts, setups=[make_setup()], decision=make_decision())

# ── ExplanationReport ──────────────────────────────────────────────────────
def test_report_type(report):         assert isinstance(report, ExplanationReport)
def test_facts_populated(report):     assert len(report.facts) == 2
def test_setups_populated(report):    assert len(report.setups) == 1
def test_decision_populated(report):  assert report.decision.get("action") == BUY
def test_summary_set(report):         assert "BUY" in report.summary or "SNRC1" in report.summary
def test_timestamp_set(report):       assert report.timestamp
def test_trace_populated(report):     assert len(report.trace_tree) > 0

# ── Trace Tree ─────────────────────────────────────────────────────────────
def test_trace_has_facts(report):
    assert any("FACTS" in l for l in report.trace_tree)
def test_trace_has_setups(report):
    assert any("SETUP" in l for l in report.trace_tree)
def test_trace_has_decision(report):
    assert any("DECISION" in l for l in report.trace_tree)

# ── JSON Export ────────────────────────────────────────────────────────────
def test_json_export(report):
    j = render_json(report)
    d = json.loads(j)
    assert "decision" in d and "facts" in d

def test_json_decision_action(report):
    d = render_dict(report)
    assert d["decision"]["action"] == BUY

def test_json_no_trading_logic(report):
    j = render_json(report)
    assert "lot_size" not in j and "stop_loss" not in j and "take_profit" not in j

# ── Markdown Export ────────────────────────────────────────────────────────
def test_markdown_export(report):
    md = render_markdown(report)
    assert "Decision" in md and "SNRC1" in md

def test_markdown_has_facts(report):
    md = render_markdown(report)
    assert "trend" in md or "session" in md

def test_markdown_has_trace(report):
    md = render_markdown(report)
    assert "TRACE" in md or "FACTS" in md or "DECISION" in md

# ── No trading logic ──────────────────────────────────────────────────────
def test_generator_no_buy_sell_output(gen):
    r = gen.generate(decision=TradeDecision(action=WAIT, reason="no setup"))
    assert r.decision.get("action") == WAIT  # only reflects, never decides

def test_generator_no_yaml_read(gen):
    import inspect, core.explanation.explanation_generator as eg
    src = inspect.getsource(eg)
    assert "yaml.safe_load" not in src
    assert "open(" not in src
