"""Query Registry — named saved queries for reuse."""
from typing import Any, Callable, Dict, List, Optional


class QueryRegistry:
    def __init__(self):
        self._store: Dict[str, Callable] = {}

    def register(self, name: str, fn: Callable) -> None:
        self._store[name] = fn

    def execute(self, name: str, *args, **kwargs) -> Any:
        if name not in self._store:
            raise KeyError(f"Query not registered: {name}")
        return self._store[name](*args, **kwargs)

    def list(self) -> List[str]:
        return list(self._store.keys())
