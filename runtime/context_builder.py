"""ExecutionContext — runtime context from market, memory, metadata."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class ExecutionContext:
    market: Dict[str, Any] = field(default_factory=dict)
    memory: Dict[str, Any] = field(default_factory=dict)
    runtime: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    execution_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def merge(self, other: 'ExecutionContext') -> 'ExecutionContext':
        """Merge another context into this one."""
        return ExecutionContext(
            market={**self.market, **other.market},
            memory={**self.memory, **other.memory},
            runtime={**self.runtime, **other.runtime},
            timestamp=self.timestamp,
            execution_id=self.execution_id or other.execution_id,
            metadata={**self.metadata, **other.metadata},
        )
