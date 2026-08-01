"""Binance public REST loader — no auth, no ccxt dep.

Primary for BTCUSD.
ponytail: add auth + more pairs when needed.
"""
from __future__ import annotations
import logging
import requests
import pandas as pd
from backtest.loaders.registry import register

log = logging.getLogger("binance_loader")

_SYMBOL_MAP = {
    "BTCUSD":  "BTCUSDT",
    "XAUUSD":  "XAUUSDT",
    "GBPJPY":  "GBPJPY",
}

_TF_MAP = {
    "M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m",
    "H1": "1h", "H4": "4h", "D1":  "1d",
}

_URL = "https://api.binance.com/api/v3/klines"


@register("binance", markets=["BTCUSD"])
def load_binance(symbol: str, timeframe: str, count: int = 200) -> pd.DataFrame:
    ticker   = _SYMBOL_MAP.get(symbol.upper(), symbol.upper())
    interval = _TF_MAP.get(timeframe.upper(), "5m")
    limit    = min(count, 1000)

    resp = requests.get(_URL, params={"symbol": ticker, "interval": interval, "limit": limit}, timeout=10)
    resp.raise_for_status()
    raw = resp.json()

    # Binance klines: [open_time, open, high, low, close, volume, ...]
    df = pd.DataFrame(raw, columns=[
        "time", "open", "high", "low", "close", "volume",
        "close_time", "quote_vol", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore"
    ])
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df = df[["time", "open", "high", "low", "close", "volume"]].copy()
    df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})
    df.sort_values("time", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df.tail(count).reset_index(drop=True)
