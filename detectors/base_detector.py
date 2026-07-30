import logging
from typing import List, Dict, Any, Optional
from core.detectors.detector_interface import DetectorInterface
from core.detectors.fact import Fact
from core.context.context_model import MarketContext

logger = logging.getLogger("BystraBaseDetector")

class BystraBaseDetector(DetectorInterface):
    """Base detector for all Bystra patterns."""
    
    def __init__(self):
        super().__init__()

    def initialize(self, config: Dict[str, Any]) -> None:
        pass

    def validate(self, context: MarketContext) -> bool:
        return True

    def metadata(self) -> Dict[str, Any]:
        return {"name": self.__class__.__name__}

    def health_check(self) -> bool:
        return True

    def _create_pattern_fact(self, pattern_type: str, confidence: float, metadata: Dict[str, Any]) -> Fact:
        return Fact(
            detector_id=self.__class__.__name__,
            fact_type="ENTRY_PATTERN",
            value=pattern_type,
            confidence=confidence,
            metadata=metadata
        )

    def _get_candles(self, context: MarketContext, timeframe: str, count: int) -> List[Any]:
        """Helper to extract candles from context metadata or history."""
        return context.metadata.get("candles", {}).get(timeframe, [])[:count]
