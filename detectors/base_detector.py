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
        """Helper to extract candles from context metadata or history.
        Returns the LAST `count` candles (most recent), in chronological order.
        Gateway returns oldest-first, so [-count:] gives latest window.
        """
        all_candles = context.metadata.get("candles", {}).get(timeframe, [])
        return all_candles[-count:] if len(all_candles) > count else all_candles

    def _get_features(self, context: Any):
        """Get FeatureSnapshot if injected via ScanContext/metadata. Returns None if unavailable."""
        # ScanContext path
        if hasattr(context, "features"):
            return context.features
        # Legacy MarketContext path (features injected via metadata)
        return context.metadata.get("features")

    def _get_pivots(self, candles: list, n: int = 3) -> list:
        """Swing pivots — pure math, no common.py import."""
        pivots = []
        for i in range(n, len(candles) - n):
            is_high = all(float(candles[i]["high"]) > float(candles[j]["high"]) for j in range(i-n, i)) and \
                      all(float(candles[i]["high"]) > float(candles[j]["high"]) for j in range(i+1, i+n+1))
            is_low  = all(float(candles[i]["low"])  < float(candles[j]["low"])  for j in range(i-n, i)) and \
                      all(float(candles[i]["low"])  < float(candles[j]["low"])  for j in range(i+1, i+n+1))
            if is_high:
                pivots.append({"type": "high", "price": float(candles[i]["high"]), "index": i})
            if is_low:
                pivots.append({"type": "low",  "price": float(candles[i]["low"]),  "index": i})
        return pivots
