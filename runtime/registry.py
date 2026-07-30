"""Component registry — runtime components register here."""
from typing import Any, Dict, List, Optional


class ComponentRegistry:
    def __init__(self):
        self._store: Dict[str, Any] = {}

    def register(self, name: str, component: Any) -> None:
        self._store[name] = component

    def get(self, name: str) -> Optional[Any]:
        return self._store.get(name)

    def list(self) -> List[str]:
        return list(self._store.keys())

    def exists(self, name: str) -> bool:
        return name in self._store

    def unregister(self, name: str) -> None:
        self._store.pop(name, None)
