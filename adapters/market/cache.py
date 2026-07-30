"""Market cache — in-memory, TTL, auto-update, no duplicates."""
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from adapters.market.models import Tick, Candle, MarketSnapshot


@dataclass
class CacheEntry:
    value: Any
    expires: float = 0  # epoch

    def is_expired(self) -> bool:
        return time.time() > self.expires if self.expires else False


class MarketCache:
    def __init__(self, default_ttl: int = 60):
        self._ticks: Dict[str, CacheEntry] = {}
        self._candles: Dict[str, Dict[str, CacheEntry]] = {}  # symbol -> timeframe -> entry
        self._snapshots: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._default_ttl = default_ttl

    def _set(self, store: Dict, key: str, value: Any, ttl: int = None):
        ttl = ttl or self._default_ttl
        with self._lock:
            store[key] = CacheEntry(value=value, expires=time.time() + ttl)

    def _get(self, store: Dict, key: str) -> Optional[Any]:
        with self._lock:
            entry = store.get(key)
            if entry and not entry.is_expired():
                return entry.value
            elif entry:
                del store[key]
            return None

    def set_tick(self, tick, ttl: int = None):
        self._set(self._ticks, tick.symbol, tick, ttl)

    def get_tick(self, symbol: str) -> Optional:
        return self._get(self._ticks, symbol)

    def set_candle(self, candle, ttl: int = None):
        key = candle.symbol
        tf = candle.timeframe
        if key not in self._candles:
            self._candles[key] = {}
        self._set(self._candles[key], tf, candle, ttl)

    def get_candle(self, symbol: str, timeframe: str) -> Optional:
        return self._get(self._candles.get(symbol, {}), timeframe)

    def set_snapshot(self, snap: MarketSnapshot, ttl: int = None):
        self._set(self._snapshots, snap.symbol, snap, ttl)

    def get_snapshot(self, symbol: str) -> Optional:
        return self._get(self._snapshots, symbol)

    def clear_expired(self):
        with self._lock:
            for store in [self._ticks, self._snapshots]:
                expired = [k for k, v in store.items() if v.is_expired()]
                for k in expired: del store[k]
            for sym, tfs in self._candles.items():
                expired = [tf for tf, v in tfs.items() if v.is_expired()]
                for tf in expired: del tfs[tf]