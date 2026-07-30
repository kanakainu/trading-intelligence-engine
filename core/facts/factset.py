"""FactSet — container for all active Facts from one detection cycle."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List
from core.detectors.fact import Fact


@dataclass
class FactSet:
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    market: str = ""
    timeframe: str = ""
    facts: List[Fact] = field(default_factory=list)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self):
        return f"<FactSet market={self.market} facts={len(self.facts)} conflicts={len(self.conflicts)}>"
