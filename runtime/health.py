"""Runtime health monitor — aggregates status from all components."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class RuntimeHealth:
    runtime_status: str = ""
    adapters_status: Dict[str, str] = field(default_factory=dict)
    compiler_status: str = ""
    memory_status: str = ""
    active_pipeline: Optional[str] = None
    uptime_seconds: float = 0.0
    last_error: Optional[str] = None
    processed_events: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runtime_status": self.runtime_status,
            "adapters_status": self.adapters_status,
            "compiler_status": self.compiler_status,
            "memory_status": self.memory_status,
            "active_pipeline": self.active_pipeline,
            "uptime_seconds": round(self.uptime_seconds, 2),
            "last_error": self.last_error,
            "processed_events": self.processed_events,
            "timestamp": self.timestamp.isoformat(),
        }
