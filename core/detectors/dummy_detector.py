"""DummyTrendDetector — reads Context, emits Trend fact. Proof-of-concept only."""
from typing import Any, Dict, List
from core.detectors.detector_interface import DetectorInterface
from core.detectors.fact import Fact
from core.context.context_model import MarketContext


class DummyTrendDetector(DetectorInterface):
    ID = "dummy_trend_detector"

    def initialize(self) -> None:
        pass

    def detect(self, context: MarketContext) -> List[Fact]:
        return [Fact(
            detector_id=self.ID,
            fact_type="trend",
            value=context.trend.value,
            confidence=0.9,
        )]

    def validate(self) -> bool:
        return True

    def health_check(self) -> bool:
        return True

    def metadata(self) -> Dict[str, Any]:
        return {"id": self.ID, "version": "1.0", "description": "Reads trend from context."}
