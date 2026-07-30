"""Standardized memory models — provider-agnostic. Runtime never uses HCK-specific objects."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class MemoryRecord:
    record_id: str = ""
    category: str = ""          # episodic, semantic, goal, identity, procedural
    key: str = ""
    value: Any = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None
    version: int = 1


@dataclass
class MemoryQuery:
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    since: Optional[datetime] = None
    limit: int = 50
    offset: int = 0


@dataclass
class MemoryResult:
    records: List[MemoryRecord] = field(default_factory=list)
    total: int = 0
    error: Optional[str] = None

    def __bool__(self):
        return bool(self.records) and not self.error


@dataclass
class MemoryHealthReport:
    provider: str = ""
    connected: bool = False
    available: bool = False
    latency_ms: float = 0.0
    error: Optional[str] = None
    records_count: int = 0
    last_compact: Optional[str] = None