"""MT5BrokerAdapter — real MT5 broker adapter wrapping gateway_client.py.
Implements BrokerAdapterBase. No trading logic here.
"""
import sys
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from adapters.base import BaseAdapter
from adapters.lifecycle import AdapterState
from adapters.broker.base import BrokerAdapterBase
from adapters.broker.models import (
    OrderRequest, OrderResponse, Position, AccountInfo,
)
from adapters.broker.exceptions import BrokerConnectionError, SymbolNotFoundError

log = logging.getLogger("MT5BrokerAdapter")


def _get_gateway_client(base_url, token, timeout):
    """Lazy import of gateway_client — enables mocking in tests."""
    sys.path.insert(0, "/home/ubuntu/.hermes/trading")
    from gateway_client import MT5GatewayClient
    return MT5GatewayClient(base_url, token, timeout=timeout)


class MT5BrokerAdapter(BrokerAdapterBase):
    """
    Production MT5 adapter built on existing MT5GatewayClient.
    Converts OrderRequest → gateway buy/sell/modify/close.
    """

    def __init__(self, base_url: str, token: str, timeout: int = 15):
        super().__init__()
        self._config = {"base_url": base_url, "token": token, "timeout": timeout}

    @property
    def name(self) -> str:
        return "mt5_broker"

    def initialize(self) -> None:
        try:
            client = _get_gateway_client(
                self._config["base_url"],
                self._config["token"],
                self._config["timeout"],
            )
            # Quick health check
            h = client.health()
            if not h:
                raise BrokerConnectionError("MT5 gateway health check returned empty")
            self._client = client
            self._set_state(AdapterState.INITIALIZED)
            log.info("MT5BrokerAdapter initialized OK")
        except Exception as e:
            self._set_state(AdapterState.FAILED)
            raise BrokerConnectionError(f"MT5 init failed: {e}") from e

    def connect(self) -> None:
        self._set_state(AdapterState.CONNECTED)

    def disconnect(self) -> None:
        self._client = None
        self._set_state(AdapterState.DISCONNECTED)

    # ── Account ────────────────────────────────────────────────────────────
    def health_check(self):
        try:
            h = self._client.health()
            return self._health(error=None)
        except Exception as e:
            return self._health(error=str(e))

    def get_account_info(self) -> AccountInfo:
        raw = self._client.account()
        return AccountInfo(
            balance=float(raw.get("balance", 0)),
            equity=float(raw.get("equity", 0)),
            margin=float(raw.get("margin", 0)),
            free_margin=float(raw.get("margin_free", 0)),
            margin_level=float(raw.get("margin_level", 0)),
            currency=raw.get("currency", "USD"),
            leverage=int(raw.get("leverage", 1)),
        )

    def get_balance(self) -> float: return self.get_account_info().balance
    def get_equity(self) -> float: return self.get_account_info().equity

    def get_margin_status(self) -> Dict[str, float]:
        a = self.get_account_info()
        return {"margin": a.margin, "free_margin": a.free_margin, "margin_level": a.margin_level}

    # ── Market ─────────────────────────────────────────────────────────────
    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        return self._client.market_info(symbol.upper()) or {}

    def get_spread(self, symbol: str) -> float:
        info = self.get_symbol_info(symbol)
        return float(info.get("spread", 0))

    # ── Orders ─────────────────────────────────────────────────────────────
    def submit_order(self, req: OrderRequest) -> OrderResponse:
        direction = req.side.lower()
        if direction == "buy":
            ticket = self._client.buy(req.symbol.upper(), req.volume,
                                      sl=req.stop_loss, tp=req.take_profit,
                                      comment=req.comment)
        elif direction == "sell":
            ticket = self._client.sell(req.symbol.upper(), req.volume,
                                       sl=req.stop_loss, tp=req.take_profit,
                                       comment=req.comment)
        else:
            return OrderResponse(status="REJECTED", error=f"Unknown side: {req.side}")

        if ticket is not None:
            return OrderResponse(order_id=str(ticket), status="FILLED",
                                 filled_volume=req.volume)
        return OrderResponse(status="REJECTED", error="Order not accepted")

    def modify_order(self, order_id: str, **kwargs) -> OrderResponse:
        try:
            result = self._client.modify(
                int(order_id),
                sl=kwargs.get("stop_loss"),
                tp=kwargs.get("take_profit"),
            )
            success = result.get("success", False) if isinstance(result, dict) else bool(result)
            return OrderResponse(
                order_id=order_id,
                status="FILLED" if success else "REJECTED",
            )
        except Exception as e:
            return OrderResponse(order_id=order_id, status="REJECTED", error=str(e))

    def cancel_order(self, order_id: str) -> bool:
        return True  # MT5: market orders can't be cancelled after filled

    # ── Positions ──────────────────────────────────────────────────────────
    def get_positions(self) -> List[Position]:
        raw_list = self._client.positions()
        result = []
        for p in raw_list:
            ts_raw = p.get("time") or p.get("open_time")
            ts = (
                datetime.fromtimestamp(ts_raw, tz=timezone.utc)
                if isinstance(ts_raw, (int, float))
                else datetime.now(tz=timezone.utc)
            )
            result.append(Position(
                position_id=str(p.get("ticket", "")),
                symbol=p.get("symbol", ""),
                side=(p.get("direction") or p.get("type", "")).upper(),
                volume=float(p.get("volume", 0)),
                entry_price=float(p.get("open_price") or p.get("price_open") or 0),
                stop_loss=p.get("sl"),
                take_profit=p.get("tp"),
                unrealized_profit=float(p.get("profit", 0)),
                open_time=ts,
                comment=p.get("comment", ""),  # Add comment for strategy identification
            ))
        return result

    def close_position(self, position_id: str) -> OrderResponse:
        try:
            ok = self._client.close(int(position_id))
            return OrderResponse(order_id=position_id,
                                 status="FILLED" if ok else "REJECTED")
        except Exception as e:
            return OrderResponse(order_id=position_id, status="REJECTED", error=str(e))


    def get_orders(self) -> List[OrderResponse]:
        return []  # MT5: no pending orders in scalping mode, return empty list to fulfill abstract contract

    def get_closed_trades(self, days: int = 1) -> List[Position]:
        # Fallback for gateways that don't expose trade history directly.
        # This will need to be improved if a history endpoint becomes available.
        log.warning("MT5 gateway does not expose a direct 'history/deals' or 'account/history' endpoint. Returning empty list for closed trades.")
        return []
