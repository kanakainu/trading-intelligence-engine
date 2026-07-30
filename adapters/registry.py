"""Adapter registry — register, load, discover adapters."""
from typing import Dict, List, Optional, Type
from adapters.base import BaseAdapter


class AdapterRegistry:
    def __init__(self):
        self._store: Dict[str, Type[BaseAdapter]] = {}

    def register(self, name: str, adapter_cls: Type[BaseAdapter]) -> None:
        self._store[name] = adapter_cls

    def load(self, name: str) -> Optional[BaseAdapter]:
        cls = self._store.get(name)
        return cls() if cls else None

    def discover(self) -> List[str]:
        return list(self._store.keys())

    def available(self, name: str) -> bool:
        return name in self._store
