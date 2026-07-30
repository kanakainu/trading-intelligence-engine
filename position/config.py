"""Position Manager configuration."""
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class PositionConfig:
    auto_sync: bool = True
    sync_interval_seconds: int = 60
    max_history_positions: int = 1000
    allow_partial_close: bool = True
    partial_close_threshold: float = 0.25  # min fraction 0.0-1.0
    params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def default(cls) -> 'PositionConfig':
        return cls()
