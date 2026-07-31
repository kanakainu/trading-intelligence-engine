"""StrategyConfig — base config every strategy must subclass."""
from dataclasses import dataclass, field
from typing import List


@dataclass
class StrategyConfig:
    """Base config. Subclass and add strategy-specific fields."""
    min_confidence: float = 0.65
    max_signals_per_scan: int = 1
    enabled: bool = True
    enabled_symbols: List[str] = field(default_factory=list)
    enabled_timeframes: List[str] = field(default_factory=list)
