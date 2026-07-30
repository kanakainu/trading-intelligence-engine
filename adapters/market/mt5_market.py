"""MT5MarketAdapter — live market data from MT5 Gateway via HTTP polling.
Implements MarketAdapterBase. No trading logic. No BUY/SELL.
"""
import sys
import logging
import time
import threading
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from adapters.base import BaseAdapter
from adapters.lifecycle import AdapterState
from adapters.market.base import MarketAdapterBase
from adapters.market.models import Tick, Candle, MarketSnapshot

log = logging.getLogger("MT5MarketAdapter")


def _get_gateway_client(base_url, token, timeout):
    sys.path.insert(0, "/home/ubuntu/.hermes/trading")
    from gateway_client import MT5GatewayClient
    return MT5GatewayClient(base_url, token, timeout=timeout)


class MT5MarketAdapter(MarketAdapterBase):
    """
    Live market data adapter. Polls MT5 Gateway HTTP for ticks/candles.
    No WebSocket dependency — uses existing gateway_client.py endpoints.

    subscribe(symbol)   → starts polling thread
    get_latest_tick     → returns last tick from cache
    get_latest_candle   → returns last candle from cache
    get_market_snapshot → builds snapshot from cached data
    """

    def __init__(self, base_url: str, token: str,
                 poll_interval: float = 1.0, timeout: int = 10):
        super().__init__()
        self._config = {
            "base_url": base_url,
            "token": token,
            "poll_interval": poll_interval,
            "timeout": timeout,
        }
        self._client: Any = None
        self._subscribed: Dict[str, bool] = {}
        self._ticks: Dict[str, Dict] = {}
        self._candles: Dict[str, List[Dict]] = {}
        self._poll_threads: Dict[str, threading.Thread] = {}
        self._stop_event = threading.Event()
        self._on_tick: Optional[Callable] = None

    @property
    def name(self) -> str:
        return "mt5_market"

    def initialize(self) -> None:
        try:
            self._client = _get_gateway_client(
                self._config["base_url"],
                self._config["token"],
                self._config["timeout"],
            )
            h = self._client.health()
            if not h:
                raise ConnectionError("MT5 health empty")
            self._set_state(AdapterState.INITIALIZED)
            log.info("MT5MarketAdapter initialized OK")
        except Exception as e:
            self._set_state(AdapterState.FAILED)
            log.error(f"MT5MarketAdapter init failed: {e}")
            self._set_state(AdapterState.INITIALIZED)  # allow retry

    def connect(self) -> None:
        self._set_state(AdapterState.CONNECTED)

    def disconnect(self) -> None:
        self._stop_event.set()
        for sym, t in self._poll_threads.items():
            t.join(timeout=3)
        self._poll_threads.clear()
        self._subscribed.clear()
        self._client = None
        self._set_state(AdapterState.DISCONNECTED)

    def set_on_tick(self, callback: Callable) -> None:
        """Register callback for each tick: callback(symbol, tick_dict)"""
        self._on_tick = callback

    # ── Subscriptions ──────────────────────────────────────────────────────
    def subscribe(self, symbol: str) -> None:
        sym = symbol.upper()
        if sym in self._subscribed:
            return
        self._subscribed[sym] = True
        self._stop_event.clear()
        t = threading.Thread(target=self._poll_loop, args=(sym,), daemon=True)
        self._poll_threads[sym] = t
        t.start()
        log.info(f"Subscribed: {sym}")

    def unsubscribe(self, symbol: str) -> None:
        sym = symbol.upper()
        self._subscribed.pop(sym, None)
        self._poll_threads.pop(sym, None)
        self._ticks.pop(sym, None)
        self._candles.pop(sym, None)

    def _poll_loop(self, symbol: str) -> None:
        while not self._stop_event.is_set():
            try:
                # Fetch price
                price_data = self._client.price(symbol)
                if price_data:
                    self._ticks[symbol] = {
                        "symbol": symbol,
                        "bid": float(price_data.get("bid", 0)),
                        "ask": float(price_data.get("ask", 0)),
                        "spread": float(price_data.get("spread", 0)),
                        "volume": float(price_data.get("volume", 0)),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "raw": price_data,
                    }
                    if self._on_tick:
                        self._on_tick(symbol, self._ticks[symbol])

                # Fetch latest candle (M5)
                candle_data = self._client.candles(symbol, "M5", 1)
                if candle_data and isinstance(candle_data, list) and candle_data:
                    c = candle_data[0]
                    self._candles.setdefault(symbol, [])
                    self._candles[symbol] = [c] + self._candles[symbol][:19]

            except Exception as e:
                log.debug(f"Poll error {symbol}: {e}")

            time.sleep(self._config["poll_interval"])

    # ── Data Access ────────────────────────────────────────────────────────
    def get_latest_tick(self, symbol: str) -> Optional[Tick]:
        t = self._ticks.get(symbol.upper())
        if not t:
            return None
        return Tick(
            symbol=t["symbol"],
            bid=Decimal(str(t["bid"])),
            ask=Decimal(str(t["ask"])),
            spread=Decimal(str(t["spread"])),
            timestamp=datetime.now(timezone.utc),
            volume=Decimal(str(t.get("volume", 0))) if t.get("volume") else None,
        )

    def get_latest_candle(self, symbol: str, timeframe: str = "M5") -> Optional[Candle]:
        candles = self._candles.get(symbol.upper(), [])
        if not candles:
            return None
        c = candles[0]
        return Candle(
            symbol=symbol.upper(),
            timeframe=timeframe,
            open=Decimal(str(c.get("open", 0))),
            high=Decimal(str(c.get("high", 0))),
            low=Decimal(str(c.get("low", 0))),
            close=Decimal(str(c.get("close", 0))),
            volume=Decimal(str(c.get("volume", 0))),
            timestamp=datetime.now(timezone.utc),
        )

    def get_market_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        t = self._ticks.get(symbol.upper())
        if not t:
            return None
        raw = t.get("raw", {})
        last_price = float(raw.get("last_price", 0) or t["bid"] or t["ask"])
        return MarketSnapshot(
            symbol=symbol.upper(),
            last_price=Decimal(str(last_price)),
            spread=Decimal(str(t["spread"])),
            timestamp=datetime.now(timezone.utc),
            metadata={"bid": t["bid"], "ask": t["ask"]},
        )

    def health_check(self):
        try:
            h = self._client.health()
            return self._health(error=None)
        except Exception as e:
            return self._health(error=str(e))
