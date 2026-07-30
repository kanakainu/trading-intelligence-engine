"""Candidate — hypothesis that a Setup is forming. No BUY/SELL."""
from dataclasses import dataclass, field
from typing import List


@dataclass
class Candidate:
    setup_id: str
    setup_name: str
    score: float                      # 0.0 – 1.0
    status: str                       # MATCH | PARTIAL | NO_MATCH
    matched_dependencies: List[str] = field(default_factory=list)
    missing_dependencies: List[str] = field(default_factory=list)
    warnings: List[str]               = field(default_factory=list)
    reason: str = ""

    def __repr__(self):
        return f"<Candidate {self.setup_id} {self.status} score={self.score:.0%}>"
