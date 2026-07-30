"""PatternRegistry — store/recall compiled PatternDefinitions."""
from typing import Dict, List, Optional
from core.patterns.pattern_definition import PatternDefinition


class PatternRegistry:
    def __init__(self):
        self._store: Dict[str, PatternDefinition] = {}

    def register(self, pattern: PatternDefinition) -> None:
        self._store[pattern.id] = pattern

    def get(self, pattern_id: str) -> Optional[PatternDefinition]:
        return self._store.get(pattern_id)

    def list(self) -> List[str]:
        return list(self._store.keys())

    def all(self) -> List[PatternDefinition]:
        return list(self._store.values())

    def exists(self, pattern_id: str) -> bool:
        return pattern_id in self._store
