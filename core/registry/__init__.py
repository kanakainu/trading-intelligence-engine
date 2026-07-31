"""Strategy Registry Package — Dynamic strategy loading.

Usage:
    from core.registry import get_strategy_registry, register_strategy, StrategyMetadata
    
    # Register
    metadata = StrategyMetadata(
        name="Bystra",
        version="1.0.0",
        description="Bystra scalping methodology",
        author="Mas Wisnu",
        supported_symbols=["XAUUSD", "BTCUSD"],
        default_risk_pct=1.0,
        tags=["scalping", "swing"]
    )
    
    def bystra_factory(**kwargs):
        from strategy.orchestrator import StrategyOrchestrator
        return StrategyOrchestrator(**kwargs)
    
    register_strategy("Bystra", bystra_factory, metadata)
    
    # List
    registry = get_strategy_registry()
    print(registry.list_enabled())
    
    # Instantiate
    strategy = registry.instantiate("Bystra", param1=val1)
"""
from core.registry.registry_models import (
    StrategyMetadata,
    StrategyEntry,
)
from core.registry.strategy_registry import (
    StrategyRegistry,
    get_strategy_registry,
    register_strategy,
)

__all__ = [
    "StrategyMetadata",
    "StrategyEntry",
    "StrategyRegistry",
    "get_strategy_registry",
    "register_strategy",
]

__version__ = "1.0.0"