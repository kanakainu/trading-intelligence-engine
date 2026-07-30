"""Broker registry — register/load broker adapters."""
from typing import Dict, List, Optional, Type
from adapters.broker.base import BrokerAdapterBase


class BrokerRegistry:
    def __init__(self):
        self._store: Dict[str, Type[BrokerAdapterBase]] = {}

    def register(self, name: str, cls: Type[BrokerAdapterBase]) -> None:
        self._store[name] = cls

    def load(self, name: str) -> Optional[BrokerAdapterBase]:
        cls = self._store.get(name)
        return cls() if cls else None

    def list(self) -> List[str]:
        return list(self._store.keys())

    def exists(self, name: str) -> bool:
        return name in self._store
