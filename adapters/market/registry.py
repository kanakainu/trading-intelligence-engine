"""Market Data Registry — register/load/discover market adapters."""
from typing import Dict, List, Optional, Type
from adapters.market.base import MarketAdapterBase


class MarketRegistry:
    def __init__(self):
        self._store: Dict[str, Type[MarketAdapterBase]] = {}

    def register(self, name: str, adapter_cls) -> None:
        self._store[name] = adapter_cls

    def load(self, name: str):
        cls = self._store.get(name)
        return cls() if cls else None

    def list(self) -> list:
        return list(self._store.keys())

    def exists(self, name: str) -> bool:
        return name in self._store