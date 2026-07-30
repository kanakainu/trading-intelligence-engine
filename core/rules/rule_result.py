"""RuleResult — stores pass/fail, matched/failed facts, explanation, trace."""
from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class RuleResult:
    passed: bool
    matched: List[str] = field(default_factory=list)
    failed:  List[str] = field(default_factory=list)
    explanation: str = ""
    trace: List[str] = field(default_factory=list)

    def __repr__(self):
        return f"<RuleResult {'PASS' if self.passed else 'FAIL'} matched={len(self.matched)} failed={len(self.failed)}>"
