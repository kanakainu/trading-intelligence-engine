"""Rule — atomic and compound rule objects. No trading logic."""
from dataclasses import dataclass, field
from typing import Any, List, Optional
from core.rules.operator import Op


@dataclass
class AtomicRule:
    fact: str
    op: Op
    value: Any = None   # None for EXISTS/NOT_EXISTS

    def __repr__(self):
        return f"({self.fact} {self.op} {self.value})"


@dataclass
class CompoundRule:
    logic: str          # AND | OR | NOT
    rules: List[Any] = field(default_factory=list)  # AtomicRule or CompoundRule

    def __repr__(self):
        return f"({self.logic}: {self.rules})"
