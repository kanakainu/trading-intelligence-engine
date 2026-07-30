"""Query Cache — LRU-like dict cache. Graph built once, queries cached."""
from typing import Any, Dict, Optional


class QueryCache:
    def __init__(self, maxsize: int = 512):
        self._store: Dict[str, Any] = {}
        self._maxsize = maxsize

    def get(self, key: str) -> Optional[Any]:
        return self._store.get(key)

    def set(self, key: str, value: Any) -> None:
        if len(self._store) >= self._maxsize:
            # evict oldest key
            self._store.pop(next(iter(self._store)))
        self._store[key] = value

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)
