"""AggressiveStrategy metadata."""
from core.strategy.strategy_metadata import StrategyMetadata

AGGRESSIVE_METADATA = StrategyMetadata(
    id="aggressive_v1",
    name="Aggressive",
    version="0.1.0",
    author="TIE",
    description="High-frequency scalping — skeleton, not production-ready",
    supported_symbols=["XAUUSD", "BTCUSD"],
    supported_timeframes=["M1", "M5"],
    priority=20,
    tags=["aggressive", "scalping", "wip"],
)
