"""Broker adapter abstract interface — connect, trade, manage positions."""
from abc import abstractmethod
from typing import Any, Dict, List, Optional
from adapters.base import BaseAdapter
from adapters.lifecycle import AdapterState
from adapters.broker.models import (
    OrderRequest, OrderResponse, Position, AccountInfo
)
from adapters.broker.exceptions import BrokerConnectionError, SymbolNotFoundError


class BrokerAdapterBase(BaseAdapter):
    """Every broker adapter (MT5, REST, FIX) implements this."""

    @abstractmethod
    def get_account_info(self) -> AccountInfo: ...
    @abstractmethod
    def get_balance(self) -> float: ...
    @abstractmethod
    def get_equity(self) -> float: ...
    @abstractmethod
    def get_margin_status(self) -> Dict[str, float]: ...
    @abstractmethod
    def get_symbol_info(self, symbol: str) -> Dict[str, Any]: ...
    @abstractmethod
    def get_spread(self, symbol: str) -> float: ...
    @abstractmethod
    def submit_order(self, req: OrderRequest) -> OrderResponse: ...
    @abstractmethod
    def modify_order(self, order_id: str, **kwargs) -> OrderResponse: ...
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool: ...
    @abstractmethod
    def get_positions(self) -> List[Position]: ...
    @abstractmethod
    def get_orders(self) -> List[OrderResponse]: ...
    @abstractmethod
    def close_position(self, position_id: str) -> OrderResponse: ...

    def get_status(self): return self._state

    def _validate_symbol(self, symbol: str, known: set):
        if symbol not in known:
            raise SymbolNotFoundError(symbol)
