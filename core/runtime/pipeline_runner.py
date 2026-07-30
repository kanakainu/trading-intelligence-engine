"""Pipeline Runner — convenience entry point for running TIE with dummy data."""
import logging
from datetime import datetime, timezone
from core.compiler.knowledge_loader import KnowledgeLoader, KnowledgeRegistry, KnowledgeObject
from core.detectors.detector_registry import DetectorRegistry
from core.detectors.dummy_detector import DummyTrendDetector
from core.setup.setup_registry import SetupRegistry
from core.runtime.core_pipeline import CorePipeline
from core.runtime.pipeline_health import run_health_check

log = logging.getLogger(__name__)


def build_dummy_runner() -> CorePipeline:
    """Build a runnable pipeline with dummy knowledge + detector for testing."""
    reg = KnowledgeRegistry()
    for id_, cat in [("C001","Concept"), ("S001","Structure"), ("L001","Location")]:
        obj = KnowledgeObject(id=id_, name=f"Dummy {id_}", category=cat, version="1.0", status="ACTIVE")
        reg.add(obj, f"/dummy/{id_}.yaml", "abc")

    det_reg = DetectorRegistry()
    det_reg.register(DummyTrendDetector.ID, DummyTrendDetector())

    setup_reg = SetupRegistry()
    setup_reg.register({
        "id": "DUMMY_SETUP",
        "name": "Dummy Setup",
        "confidence": 0.8,
        "rules": {"fact": "trend", "op": "eq", "value": "bullish"},
    })

    pipeline = CorePipeline(
        knowledge_registry=reg,
        relationships=[],
        detector_registry=det_reg,
        setup_registry=setup_reg,
    )
    return pipeline


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pipeline = build_dummy_runner()
    market_data = {
        "symbol": "XAUUSD",
        "timeframe": "M5",
        "timestamp": datetime.now(timezone.utc),
        "market_open": True,
        "spread": 20.0,
        "candles": [{"open": p, "high": p+1, "low": p-1, "close": p, "volume": 100}
                    for p in range(100, 115)],
    }
    result = pipeline.run(market_data)
    for exp in result.explanations:
        print(exp.to_json())
