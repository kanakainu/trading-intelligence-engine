from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class SkillStatus(Enum):
    REGISTERED = "REGISTERED"
    INITIALIZED = "INITIALIZED"
    READY = "READY"
    RUNNING = "RUNNING"
    DISABLED = "DISABLED"
    FAILED = "FAILED"
    UNLOADED = "UNLOADED"


@dataclass
class SkillContext:
    market_snapshot: Dict[str, Any]
    runtime_context: Dict[str, Any] = field(default_factory=dict)
    memory_context: Dict[str, Any] = field(default_factory=dict)
    execution_context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SkillResult:
    skill_name: str
    success: bool
    confidence: float
    findings: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0


@dataclass
class SkillHealth:
    name: str
    status: SkillStatus
    evaluations: int = 0
    failures: int = 0
    avg_execution_ms: float = 0.0
    last_error: Optional[str] = None
