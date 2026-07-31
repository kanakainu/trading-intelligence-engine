"""Bystra Strategy Metadata."""
from core.strategy.strategy_metadata import StrategyMetadata

BYSTRA_METADATA = StrategyMetadata(
    id="bystra_v1",
    name="Bystra",
    version="1.0.0",
    author="TIE",
    description="Supply/demand zone: RBR/DBD/QM + HTF confluence",
    supported_symbols=["XAUUSD", "BTCUSD", "GBPJPY"],
    supported_timeframes=["M5", "M15", "M30", "H1"],
    supported_regimes=["TRENDING", "RANGE", "EARLY_TREND"],
    priority=10,
    tags=["bystra", "supply_demand", "swing"],
)
