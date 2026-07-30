"""Memory Registry — register/load/discover/switch memory providers."""
from typing import Dict, List, Optional, Type
from adapters.memory.base import MemoryAdapterBase


class MemoryRegistry:
    def __init__(self):
        self._store: Dict[str, Type[MemoryAdapterBase]] = {}

    def register(self, name: str, cls: Type[MemoryAdapterBase]) -> None:
        self._store[name] = cls

    def load(self, name: str) -> Optional[MemoryAdapterBase]:
        cls = self._store.get(name)
        return cls() if cls else None

    def list(self) -> List[str]:
        return list(self._store.keys())

    def exists(self, name: str) -> bool:
        return name in self._store

    def switch(self, _from: str, to: str) -> Optional[MemoryAdapterBase]:
        """Switch active provider. Does NOT touch HCK internals."""
        return self.load(to)