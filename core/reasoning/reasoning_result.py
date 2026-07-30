"""Reasoning Result — output of Reasoning Engine."""
from dataclasses import dataclass, field
from typing import Any, Dict, List
from core.reasoning.candidate import Candidate


@dataclass
class ReasoningResult:
    candidates: List[Candidate] = field(default_factory=list)
    warnings: List[str]         = field(default_factory=list)

    @property
    def best(self):
        return self.candidates[0] if self.candidates else None

    @property
    def matched(self):
        return [c for c in self.candidates if c.status == "MATCH"]

    @property
    def partial(self):
        return [c for c in self.candidates if c.status == "PARTIAL"]

    def __repr__(self):
        return f"<ReasoningResult candidates={len(self.candidates)} matched={len(self.matched)}>"
