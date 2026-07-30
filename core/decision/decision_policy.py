"""DecisionPolicy — min confidence threshold, setup priority. No trading logic."""
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class DecisionPolicy:
    min_confidence: float = 0.65
    setup_priority: Dict[str, int] = field(default_factory=dict)  # setup_id → priority (lower=better)
    prefer_methodology: str = ""  # e.g. "bystra" — empty = no preference
