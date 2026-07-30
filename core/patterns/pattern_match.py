"""PatternMatch — result of pattern matching. No trading logic."""
from dataclasses import dataclass, field
from typing import List

MATCH         = "MATCH"
PARTIAL_MATCH = "PARTIAL_MATCH"
NO_MATCH      = "NO_MATCH"


@dataclass
class PatternMatch:
    pattern_id: str
    pattern_name: str
    status: str               # MATCH | PARTIAL_MATCH | NO_MATCH
    score: float              # 0.0–1.0
    matched_rules: List[str] = field(default_factory=list)
    failed_rules:  List[str] = field(default_factory=list)
    explanation:   str = ""
    dependency_trace: List[str] = field(default_factory=list)

    def __repr__(self):
        return f"<PatternMatch {self.pattern_id} {self.status} score={self.score:.0%}>"
