"""Internal runtime events — event-driven orchestration."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict
from enum import Enum


class EventType(str, Enum):
    MARKET_UPDATED           = "MARKET_UPDATED"
    CONTEXT_READY            = "CONTEXT_READY"
    FACTS_COMPILED           = "FACTS_COMPILED"
    REASONING_COMPLETED      = "REASONING_COMPLETED"
    DECISION_READY           = "DECISION_READY"
    EXECUTION_CONTRACT_CREATED = "EXECUTION_CONTRACT_CREATED"
    RUNTIME_WARNING          = "RUNTIME_WARNING"
    RUNTIME_ERROR            = "RUNTIME_ERROR"


@dataclass
class RuntimeEvent:
    event_type: EventType
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    execution_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
