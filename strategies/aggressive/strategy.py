"""AggressiveStrategy — skeleton only. No logic yet."""
from typing import Optional
from core.strategy.base_strategy import BaseStrategy
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.lifecycle.lifecycle_models import PositionSnapshot
from core.learning.learning_models import TradeReflection
from strategies.aggressive.metadata import AGGRESSIVE_METADATA


class AggressiveStrategy(BaseStrategy):
    """Aggressive scalping strategy — skeleton. Detectors/filters/exits TBD."""

    def __init__(self):
        super().__init__(AGGRESSIVE_METADATA)

    def initialize(self) -> None:
        self._initialized = True

    def observe(self, context: StrategyContext) -> None:
        pass

    def analyze(self, context: StrategyContext) -> StrategyResult:
        return StrategyResult(signal=None, confidence=0.0, reason="not_implemented")

    def manage_position(self, position: PositionSnapshot, context: StrategyContext) -> Optional[StrategyResult]:
        return None

    def learn(self, reflection: TradeReflection) -> None:
        pass

    def shutdown(self) -> None:
        self._initialized = False
