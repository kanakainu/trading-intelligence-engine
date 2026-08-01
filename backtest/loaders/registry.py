"""DataLoaderRegistry — P1 Data Layer.

Usage:
    from backtest.loaders.registry import load

    df = load('XAUUSD', 'M5', 200)  # returns pd.DataFrame OHLCV UTC
"""
from __future__ import annotations
import logging
from typing import Optional
import pandas as pd

log = logging.getLogger("DataLoader")

_REGISTRY: dict = {}  # name → loader_fn


def register(name: str, markets: list[str]):
    """Decorator to register a loader function."""
    def decorator(fn):
        _REGISTRY[name] = {"fn": fn, "markets": markets}
        return fn
    return decorator


# Fallback chain per symbol
_FALLBACK: dict[str, list[str]] = {
    "XAUUSD":  ["mt5",     "yahoo"],
    "BTCUSD":  ["binance", "yahoo"],
    "GBPJPY":  ["mt5",     "stooq"],
    # generic fallback
    "__default__": ["mt5", "yahoo"],
}


def load(
    symbol: str,
    timeframe: str,
    count: int = 200,
    loader: Optional[str] = None,
) -> pd.DataFrame:
    """Load OHLCV bars. Tries fallback chain until one succeeds.

    Returns DataFrame with columns: [time, open, high, low, close, volume]
    time = UTC datetime. Raises RuntimeError if all sources fail.
    """
    chain = [loader] if loader else _FALLBACK.get(symbol.upper(), _FALLBACK["__default__"])

    last_err = None
    for name in chain:
        entry = _REGISTRY.get(name)
        if entry is None:
            log.warning("Loader '%s' not registered — skip", name)
            continue
        try:
            df = entry["fn"](symbol, timeframe, count)
            if df is not None and not df.empty:
                log.info("Loaded %d bars %s %s via %s", len(df), symbol, timeframe, name)
                return df
        except Exception as e:
            last_err = e
            log.warning("Loader '%s' failed for %s: %s", name, symbol, e)

    raise RuntimeError(f"All loaders failed for {symbol}/{timeframe}. Last: {last_err}")
