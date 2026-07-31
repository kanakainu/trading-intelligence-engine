"""Base Strategy — interface for all strategies."""
from abc import ABC, abstractmethod
from typing import Optional

from core.strategy.strategy_metadata import StrategyMetadata
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.lifecycle.lifecycle_models import PositionSnapshot
from core.learning.learning_models import TradeReflection


class BaseStrategy(ABC):
    """
    Base interface for all trading strategies.
    
    NO execution logic.
    NO broker logic.
    NO MT5 logic.
    NO risk logic.
    
    Strategy only produces signals.
    """
    
    def __init__(self, metadata: StrategyMetadata):
        self._metadata = metadata
        self._initialized = False
    
    @property
    def id(self) -> str:
        return self._metadata.id
    
    @property
    def name(self) -> str:
        return self._metadata.name
    
    @property
    def version(self) -> str:
        return self._metadata.version
    
    @property
    def priority(self) -> int:
        return self._metadata.priority
    
    @property
    def enabled(self) -> bool:
        return self._metadata.enabled
    
    @property
    def supported_symbols(self) -> list:
        return self._metadata.supported_symbols
    
    @property
    def supported_timeframes(self) -> list:
        return self._metadata.supported_timeframes
    
    @property
    def metadata(self) -> StrategyMetadata:
        return self._metadata
    
    def initialize(self) -> None:
        """Initialize strategy (load models, cache, etc)."""
        self._initialized = True
    
    @abstractmethod
    def observe(self, context: StrategyContext) -> None:
        """Observe market state (passive monitoring)."""
        pass
    
    @abstractmethod
    def analyze(self, context: StrategyContext) -> StrategyResult:
        """Analyze market and generate signal if conditions met."""
        pass
    
    def generate_signal(self, context: StrategyContext) -> Optional[StrategyResult]:
        """Convenience wrapper for analyze."""
        if not self._initialized:
            self.initialize()
        return self.analyze(context)
    
    def manage_position(self, position: PositionSnapshot, context: StrategyContext) -> Optional[StrategyResult]:
        """Manage active position (adjust SL/TP, close early, etc)."""
        return None  # Default: no position management
    
    def learn(self, reflection: TradeReflection) -> None:
        """Learn from trade reflection (update internal state)."""
        pass  # Default: no learning
    
    def shutdown(self) -> None:
        """Cleanup strategy (save state, close connections, etc)."""
        self._initialized = False
