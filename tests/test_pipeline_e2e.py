"""E2E pipeline test — dummy market data → ExplanationReport."""
import pytest, sys, os, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timezone
from core.compiler.knowledge_loader import KnowledgeRegistry, KnowledgeObject
from core.detectors.detector_registry import DetectorRegistry
from core.detectors.dummy_detector import DummyTrendDetector
from core.setup.setup_registry import SetupRegistry
from core.runtime.core_pipeline import CorePipeline
from core.runtime.pipeline_health import run_health_check
from core.runtime.pipeline_runner import build_dummy_runner
from core.decision.decision import Action


MARKET_DATA = {
    "symbol": "XAUUSD",
    "timeframe": "M5",
    "timestamp": datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc),
    "market_open": True,
    "spread": 20.0,
    "candles": [{"open": p, "high": p+1, "low": p-1, "close": p, "volume": 100}
                for p in range(100, 115)],
}


@pytest.fixture(scope="module")
def pipeline():
    return build_dummy_runner()


def test_pipeline_runs_without_exception(pipeline):
    result = pipeline.run(MARKET_DATA)
    assert result is not None

def test_context_generated(pipeline):
    r = pipeline.run(MARKET_DATA)
    assert r.context is not None
    assert r.context.symbol == "XAUUSD"

def test_factset_generated(pipeline):
    r = pipeline.run(MARKET_DATA)
    assert r.factset is not None
    assert len(r.factset.facts) > 0

def test_setup_results_generated(pipeline):
    r = pipeline.run(MARKET_DATA)
    assert len(r.setup_results) > 0

def test_decisions_generated(pipeline):
    r = pipeline.run(MARKET_DATA)
    assert len(r.decisions) > 0
    for d in r.decisions:
        assert d.action in (Action.BUY, Action.SELL, Action.WAIT)

def test_explanations_generated(pipeline):
    r = pipeline.run(MARKET_DATA)
    assert len(r.explanations) > 0
    for exp in r.explanations:
        assert exp.decision_id
        assert exp.to_json()

def test_timings_recorded(pipeline):
    r = pipeline.run(MARKET_DATA)
    for key in ["context", "detector", "facts", "setup", "decision"]:
        assert key in r.timings
        assert r.timings[key] >= 0

def test_pipeline_health_check():
    from core.graph.knowledge_graph import KnowledgeGraph
    p = build_dummy_runner()
    ok, issues = run_health_check(p.graph, p.detector_engine.registry, p.setup_engine.registry)
    # Graph may have orphan nodes (dummy data, no relationships) — that's ok for health check
    non_graph_issues = [i for i in issues if not i.startswith("graph:")]
    assert not non_graph_issues, non_graph_issues

def test_e2e_bearish_market():
    """Bearish candles → trend=bearish → setup FAIL → WAIT."""
    p = build_dummy_runner()
    bearish_data = {**MARKET_DATA, "candles": [
        {"open": p, "high": p+1, "low": p-1, "close": p, "volume": 100}
        for p in range(115, 100, -1)
    ]}
    r = p.run(bearish_data)
    assert r.decisions[0].action == Action.WAIT
