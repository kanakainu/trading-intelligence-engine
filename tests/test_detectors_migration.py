import pytest
from core.context.context_model import MarketContext
from detectors.hybrid1_detector import Hybrid1Detector
from detectors.snrc1_detector import Snrc1Detector
from detectors.manipulation_detector import ManipulationDetector

def test_hybrid1_detection():
    from detectors.hybrid1_detector import Hybrid1Detector
    detector = Hybrid1Detector()
    ctx = MarketContext(symbol="XAUUSD", timestamp=None, trend="bearish")
    ctx.metadata["nearest_resistance"] = 100
    ctx.metadata["current_price"] = 99.8
    ctx.metadata["h1_resistance"] = 105
    ctx.metadata["h1_trend"] = "bearish"
    ctx.metadata["candles"] = {"M5": [], "M15": []}
    facts = detector.detect(ctx)
    assert isinstance(facts, list)

def test_snrc1_detection():
    detector = Snrc1Detector()
    ctx = MarketContext(symbol="XAUUSD", timestamp=None, trend="bullish")
    ctx.metadata["nearest_support"] = 100
    ctx.metadata["current_price"] = 100.2
    ctx.metadata["h1_support"] = 95.0
    ctx.metadata["h1_trend"] = "bullish"
    ctx.metadata["candles"] = {"M5": [], "M15": []}
    facts = detector.detect(ctx)
    assert isinstance(facts, list)

def test_manipulation_detection():
    from detectors.manipulation_detector import ManipulationDetector
    detector = ManipulationDetector()
    ctx = MarketContext(symbol="XAUUSD", timestamp=None)
    ctx.metadata["candles"] = {"M5": [], "M15": []}
    facts = detector.detect(ctx)
    assert isinstance(facts, list)
