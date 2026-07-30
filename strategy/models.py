from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class StrategyStatus(Enum):
    REGISTERED = "REGISTERED"
    LOADED = "LOADED"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


@dataclass
class StrategyDefinition:
    strategy_id: str
    strategy_name: str
    version: str
    required_skills: List[str] = field(default_factory=list)
    supported_symbols: List[str] = field(default_factory=list)
    supported_timeframes: List[str] = field(default_factory=list)
    execution_mode: str = "EVENT_DRIVEN"


@dataclass
class StrategyContext:
    market_context: Dict[str, Any]
    memory_context: Dict[str, Any]
    runtime_context: Dict[str, Any]
    skill_outputs: List[Any]
    execution_metadata: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class StrategyHealth:
    active_strategy: Optional[str] = None
    loaded_strategies: List[str] = field(default_factory=list)
    execution_count: int = 0
    average_runtime_ms: float = 0.0
    last_execution: Optional[datetime] = None
    status: str = "INITIALIZED"
