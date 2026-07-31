"""Strategy Framework Package — Multi-strategy platform.

Usage:
    from core.strategy import BaseStrategy, StrategyContext, StrategyResult, StrategyMetadata
    
    class MyStrategy(BaseStrategy):
        def observe(self, context: StrategyContext) -> None:
            pass
        
        def analyze(self, context: StrategyContext) -> StrategyResult:
            # Consume context.scan.features, context.scan.regime, etc
            # Return StrategyResult with signal
            pass
    
    metadata = StrategyMetadata(
        id="my_strategy_v1",
        name="My Strategy",
        version="1.0.0",
        author="Me",
        description="Description",
        supported_symbols=["XAUUSD"],
        supported_timeframes=["M5"],
        priority=50,
        enabled=True
    )
    
    strategy = MyStrategy(metadata)
    result = strategy.generate_signal(context)
"""
from core.strategy.base_strategy import BaseStrategy
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.strategy.strategy_metadata import StrategyMetadata

__all__ = [
    "BaseStrategy",
    "StrategyContext",
    "StrategyResult",
    "StrategyMetadata",
]

__version__ = "1.0.0"