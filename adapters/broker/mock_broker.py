"""Mock broker adapter — in-memory simulation for testing. No real broker."""
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from adapters.lifecycle import AdapterState
from adapters.broker.base import BrokerAdapterBase
from adapters.broker.models import (
    OrderRequest, OrderResponse, Position, AccountInfo
)
from adapters.broker.exceptions import (
    BrokerConnectionError, OrderRejectedError, SymbolNotFoundError
)


class MockBrokerAdapter(BrokerAdapterBase):
    @property
    def name(self) -> str: return "mock"

    def __init__(self):
        super().__init__()
        self._positions: List[Position] = []
        self._orders: List[OrderResponse] = []
        self._balance = 10_000.0
        self._connected = False
        self._known_symbols = {"XAUUSD", "EURUSD", "GBPUSD", "BTCUSD"}
        self._last_price = 2000.0  # XAUUSD base

    def initialize(self): self._set_state(AdapterState.INITIALIZED)
    def disconnect(self): self._set_state(AdapterState.DISCONNECTED); self._connected = False

    def connect(self):
        self._set_state(AdapterState.CONNECTED)
        self._connected = True

    def health_check(self):
        return self._health(latency=0.5 if self._connected else 0.0)

    # ── Account ───────────────────────────────────────────────────────────
    def get_account_info(self) -> AccountInfo:
        return AccountInfo(balance=self._balance, equity=self._balance, currency="USD")

    def get_balance(self) -> float:
        return self._balance

    def get_equity(self) -> float:
        return self._balance

    def get_margin_status(self) -> Dict[str, float]:
        return {"margin": 0, "free_margin": self._balance, "margin_level": 100}

    # ── Market ────────────────────────────────────────────────────────────
    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        self._validate_symbol(symbol, self._known_symbols)
        return {"symbol": symbol, "digits": 2, "min_volume": 0.01, "max_volume": 100}

    def get_spread(self, symbol: str) -> float:
        self._validate_symbol(symbol, self._known_symbols)
        return 20.0 if symbol == "XAUUSD" else 10.0

    # ── Order ─────────────────────────────────────────────────────────────
    def submit_order(self, req: OrderRequest) -> OrderResponse:
        self._validate_symbol(req.symbol, self._known_symbols)

        if req.volume < 0.01:
            return OrderResponse(status="REJECTED", error="volume too small",
                                 timestamp=datetime.now(timezone.utc))
        if req.side not in ("BUY", "SELL"):
            return OrderResponse(status="REJECTED", error=f"invalid side: {req.side}",
                                 timestamp=datetime.now(timezone.utc))

        oid = f"ord_{len(self._orders)+1:04d}"
        price = self._last_price + (1 if req.side == "BUY" else -1)
        resp = OrderResponse(order_id=oid, status="FILLED", filled_price=price,
                             filled_volume=req.volume, timestamp=datetime.now(timezone.utc))
        self._orders.append(resp)

        # track position
        self._positions.append(Position(
            position_id=f"pos_{len(self._positions)+1:04d}",
            symbol=req.symbol, side=req.side, volume=req.volume,
            entry_price=price, stop_loss=req.stop_loss, take_profit=req.take_profit,
            open_time=datetime.now(timezone.utc),
        ))
        return resp

    def modify_order(self, order_id: str, **kwargs) -> OrderResponse:
        return OrderResponse(order_id=order_id, status="MODIFIED")

    def cancel_order(self, order_id: str) -> bool:
        return True

    # ── Position ──────────────────────────────────────────────────────────
    def get_positions(self) -> List[Position]:
        return list(self._positions)

    def get_orders(self) -> List[OrderResponse]:
        return list(self._orders)

    def close_position(self, position_id: str) -> OrderResponse:
        self._positions = [p for p in self._positions if p.position_id != position_id]
        return OrderResponse(order_id=position_id, status="CLOSED",
                             timestamp=datetime.now(timezone.utc))
