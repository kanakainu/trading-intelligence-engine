"""Fact Registry — add/remove/clear/list/filter facts."""
import logging
from typing import Callable, List, Optional
from core.detectors.fact import Fact

log = logging.getLogger(__name__)


class FactRegistry:
    def __init__(self):
        self._facts: List[Fact] = []

    def add(self, fact: Fact) -> None:
        self._facts.append(fact)

    def remove(self, fact: Fact) -> None:
        self._facts = [f for f in self._facts if f is not fact]

    def clear(self) -> None:
        self._facts.clear()

    def list(self) -> List[Fact]:
        return list(self._facts)

    def filter(self, predicate: Callable[[Fact], bool]) -> List[Fact]:
        return [f for f in self._facts if predicate(f)]

    def __len__(self):
        return len(self._facts)
