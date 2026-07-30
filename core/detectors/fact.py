"""Fact — generic output of any Detector. No trading logic."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict


@dataclass
class Fact:
    detector_id: str
    fact_type: str
    value: Any
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self):
        return f"<Fact [{self.fact_type}={self.value}] by={self.detector_id} conf={self.confidence:.2f}>"
