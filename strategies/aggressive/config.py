"""AggressiveStrategy config."""
from dataclasses import dataclass
from core.strategy.strategy_config import StrategyConfig


@dataclass
class AggressiveConfig(StrategyConfig):
    min_confidence: float = 0.70
    max_signals_per_scan: int = 2
