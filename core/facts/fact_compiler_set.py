"""TypedFactSet — typed container. Extends FactSet API."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from core.facts.typed_facts import TypedFact


@dataclass
class TypedFactSet:
    symbol: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _facts: List[TypedFact] = field(default_factory=list, repr=False)

    def add(self, fact: TypedFact) -> None:
        self._facts.append(fact)

    def remove(self, fact: TypedFact) -> None:
        self._facts = [f for f in self._facts if f is not fact]

    def exists(self, name: str) -> bool:
        return any(f.name == name for f in self._facts)

    def find(self, name: str) -> Optional[TypedFact]:
        return next((f for f in self._facts if f.name == name), None)

    def find_by_type(self, fact_type: str) -> List[TypedFact]:
        return [f for f in self._facts if f.type == fact_type]

    def filter(self, predicate: Callable[[TypedFact], bool]) -> List[TypedFact]:
        return [f for f in self._facts if predicate(f)]

    def summary(self) -> Dict[str, Any]:
        return {f.name: f.value for f in self._facts}

    def __len__(self) -> int:
        return len(self._facts)

    def __repr__(self):
        return f"<TypedFactSet symbol={self.symbol} facts={len(self)}>"
