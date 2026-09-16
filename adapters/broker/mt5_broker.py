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

# [17-Sep] retry modify SL/TP — requote/timeout = gangguan sesaat, bukan penolakan.
import os as _os
MODIFY_RETRY = max(1, int(_os.environ.get("TIE_MODIFY_RETRY", "4")))
MODIFY_BACKOFF = float(_os.environ.get("TIE_MODIFY_BACKOFF", "0.6"))


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

    def _spread_cached(self, ticket, pos):
        """Spread $ simbol (fallback 0.2) — dipakai buat geser SL saat requote."""
        try:
            sym = pos.get("symbol", "XAUUSD")
            if not hasattr(self, "_spr_cache"):
                self._spr_cache = {}
            if sym not in self._spr_cache:
                _p = self._client.price(sym) or {}
                _s = _p.get("spread")
                self._spr_cache[sym] = (abs(float(_s)) / 1000.0 if _s else 0.2)
            return self._spr_cache[sym]
        except Exception:
            return 0.2

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
        """Modify SL/TP — RETRY cerdas: requote/timeout itu gangguan sesaat, JANGAN buang.

        [17-Sep fix] Dulu `except Exception -> REJECTED` tanpa retry: 1 requote = SL
        gagal geser, posisi balik ke SL awal dan kena SL padahal udah profit
        (bukti E77100 #3830163215: 3x BE-lock ditolak, akhirnya loss).
        Klasifikasi: error SESAAAT (requote/off quotes/timeout/5xx) -> coba lagi pakai
        harga terbaru; error PERMANEN (posisi gak ada, parameter invalid) -> langsung stop.
        """
        import time as _t
        sl, tp = kwargs.get("stop_loss"), kwargs.get("take_profit")
        transient_kw = ("requote", "off quote", "off quotes", "busy", "timeout",
                        "timed out", "connection", "temporarily", "try again",
                        "price changed", "invalid price", "slippage", "server")
        last = ""
        for attempt in range(1, MODIFY_RETRY + 1):
            try:
                result = self._client.modify(int(order_id), sl=sl, tp=tp)
                success = result.get("success", False) if isinstance(result, dict) else bool(result)
                if success:
                    if attempt > 1:
                        log.info("[modify %s] berhasil di percobaan %d/%d", order_id, attempt, MODIFY_RETRY)
                    return OrderResponse(order_id=order_id, status="FILLED")
                last = str((result or {}).get("message") or (result or {}).get("error") or "rejected")
                if any(k in last.lower() for k in ("not found", "invalid", "no such")):
                    break            # permanen — gak usah retry
            except Exception as e:
                last = str(e)
                code = getattr(e, "status", None)
                permanent = ("not found" in last.lower() or "invalid" in last.lower()
                             or (isinstance(code, int) and 400 <= code < 500 and code != 429
                                 and not any(k in last.lower() for k in ("requote", "price"))))
                transient = (isinstance(code, int) and (code == 429 or code >= 500)) or \
                            any(k in last.lower() for k in transient_kw)
                if permanent and not transient:
                    break
            if attempt < MODIFY_RETRY:
                # backoff + geser SL sedikit MENJAUH dari harga (MT5 nolak SL terlalu mepet
                # harga pasar / requote karena harga gerak). Arah: buat SELL SL naik sedikit,
                # buat BUY SL turun sedikit — tetap di sisi aman (bukan nambah risiko).
                try:
                    _p = self._client.positions() or []
                    _me = next((x for x in _p if str(x.get("ticket")) == str(order_id)), None)
                    if _me and sl:
                        _side = "buy" if str(_me.get("type", "")).lower() in ("0", "buy") else "sell"
                        _buf = max(0.01, self._spread_cached(order_id, _me)) * attempt
                        sl = round(sl - _buf if _side == "buy" else sl + _buf, 2)
                except Exception:
                    pass
                _t.sleep(MODIFY_BACKOFF * attempt)
        log.warning("Modify %s GAGAL %dx (%s)", order_id, MODIFY_RETRY, last[:80])
        return OrderResponse(order_id=order_id, status="REJECTED", error=last)

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
        """Fetch closed trades (DEAL_ENTRY_OUT) from gateway /account/history."""
        if not self._client:
            return []
        try:
            deals = self._client.history(days=days) or []
        except Exception as e:
            log.warning(f"Gateway history call failed: {e}")
            return []
        result = []
        for d in deals:
            try:
                ts = d.get("time") or d.get("close_time")
                ts = (
                    datetime.fromtimestamp(ts, tz=timezone.utc)
                    if isinstance(ts, (int, float))
                    else datetime.now(tz=timezone.utc)
                )
                result.append(Position(
                    position_id=str(d.get("ticket", "")),
                    symbol=d.get("symbol", ""),
                    side=(d.get("direction") or "").upper(),
                    volume=float(d.get("volume", 0) or 0),
                    entry_price=float(d.get("price", 0) or 0),
                    stop_loss=None,
                    take_profit=None,
                    unrealized_profit=0.0,
                    open_time=ts,
                    pnl=float(d.get("profit", 0) or 0),
                    comment=d.get("comment", ""),
                ))
            except Exception as e:
                log.warning(f"Skipping malformed deal {d.get('ticket')}: {e}")
        return result
