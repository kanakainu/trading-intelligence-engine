"""Strategy Template — copy this to create a new strategy."""
from typing import Any, Optional
import logging

from core.strategy.base_strategy import BaseStrategy
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.strategy.strategy_metadata import StrategyMetadata
from core.lifecycle.lifecycle_models import PositionSnapshot
from core.learning.learning_models import TradeReflection

logger = logging.getLogger(__name__)

# 1. Define metadata
_METADATA = StrategyMetadata(
    id="my_strategy_v1",
    name="MyStrategy",
    version="1.0.0",
    author="TIE",
    description="One-line description of what this strategy does.",
    supported_symbols=["XAUUSD"],
    supported_timeframes=["M5", "M15", "H1"],
    priority=50,
    tags=["template"],
)


class MyStrategy(BaseStrategy):
    """Rename this class and implement the abstract methods."""

    def __init__(self):
        super().__init__(_METADATA)

    def initialize(self) -> None:
        # Load models, warm caches, connect resources.
        self._initialized = True
        logger.info("%s initialized", self.name)

    def observe(self, context: StrategyContext) -> None:
        # Passive scan — update internal state, no signal yet.
        pass

    def analyze(self, context: StrategyContext) -> StrategyResult:
        # Run detectors/filters, return StrategyResult.
        # Return signal=None when no setup found.
        return StrategyResult(signal=None, confidence=0.0, reason="not_implemented")

    def manage_position(self, position: PositionSnapshot, context: StrategyContext) -> Optional[StrategyResult]:
        return None

    def learn(self, reflection: TradeReflection) -> None:
        pass

    def shutdown(self) -> None:
        self._initialized = False
