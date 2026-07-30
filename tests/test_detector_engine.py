import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timezone
from core.detectors.fact import Fact
from core.detectors.detector_registry import DetectorRegistry
from core.detectors.detector_engine import DetectorEngine
from core.detectors.dummy_detector import DummyTrendDetector
from core.context.context_model import MarketContext, Trend, Session, Volatility, MarketStatus


def make_context(trend=Trend.BULLISH):
    return MarketContext(
        symbol="TEST", timestamp=datetime.now(timezone.utc),
        trend=trend, session=Session.LONDON,
        atr=1.5, spread=20.0, volatility=Volatility.MEDIUM,
        market_status=MarketStatus.OPEN
    )


@pytest.fixture
def registry():
    r = DetectorRegistry()
    r.register(DummyTrendDetector.ID, DummyTrendDetector())
    return r


def test_registry_register_and_exists(registry):
    assert registry.exists(DummyTrendDetector.ID)

def test_registry_list(registry):
    assert DummyTrendDetector.ID in registry.list()

def test_registry_get(registry):
    d = registry.get(DummyTrendDetector.ID)
    assert d is not None

def test_registry_unregister(registry):
    registry.unregister(DummyTrendDetector.ID)
    assert not registry.exists(DummyTrendDetector.ID)

def test_dummy_detector_emits_fact():
    d = DummyTrendDetector()
    d.initialize()
    facts = d.detect(make_context(Trend.BEARISH))
    assert len(facts) == 1
    assert facts[0].fact_type == "trend"
    assert facts[0].value == "bearish"
    assert facts[0].confidence == 0.9

def test_detector_engine_aggregates_facts(registry):
    engine = DetectorEngine(registry)
    facts = engine.run(make_context())
    assert len(facts) == 1
    assert facts[0].fact_type == "trend"

def test_detector_engine_handles_failure(registry):
    class BrokenDetector(DummyTrendDetector):
        ID = "broken"
        def detect(self, context):
            raise RuntimeError("simulated failure")
    registry.register("broken", BrokenDetector())
    engine = DetectorEngine(registry)
    facts = engine.run(make_context())  # must not raise
    assert any(f.fact_type == "trend" for f in facts)

def test_detector_engine_skips_unhealthy(registry):
    class UnhealthyDetector(DummyTrendDetector):
        ID = "unhealthy"
        def health_check(self): return False
    registry.register("unhealthy", UnhealthyDetector())
    engine = DetectorEngine(registry)
    facts = engine.run(make_context())
    ids = [f.detector_id for f in facts]
    assert "unhealthy" not in ids

def test_fact_repr():
    f = Fact(detector_id="d1", fact_type="trend", value="bullish", confidence=0.9)
    assert "trend" in repr(f)

def test_dummy_detector_metadata():
    d = DummyTrendDetector()
    m = d.metadata()
    assert "id" in m and m["id"] == DummyTrendDetector.ID
