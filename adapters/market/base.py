"""Abstract Market Data Adapter — provider-agnostic."""
from abc import abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from adapters.base import BaseAdapter
from adapters.lifecycle import AdapterState
from adapters.market.models import Tick, Candle, MarketSnapshot, HealthReport


class MarketAdapterBase(BaseAdapter):
    @abstractmethod
    def subscribe(self, symbol: str) -> None: ...
    @abstractmethod
    def unsubscribe(self, symbol: str) -> None: ...

    @abstractmethod
    def get_latest_tick(self, symbol: str) -> Optional[Tick]: ...
    @abstractmethod
    def get_latest_candle(self, symbol: str, timeframe: str) -> Optional[Candle]: ...
    @abstractmethod
    def get_market_snapshot(self, symbol: str) -> Optional[MarketSnapshot]: ...

    def subscribe_all(self, symbols: List[str]) -> None:
        for s in symbols: self.subscribe(s)

    def unsubscribe_all(self, symbols: List[str]) -> None:
        for s in symbols: self.unsubscribe(s)

    def get_status(self) -> str: return self._state.value