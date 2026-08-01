"""Yahoo Finance loader — pure requests, no yfinance dep.

Fallback for XAUUSD (XAU=X) and BTCUSD (BTC-USD).
ponytail: switch to yfinance if Yahoo changes v8 API schema.
"""
from __future__ import annotations
import logging
import time
import requests
import pandas as pd
from backtest.loaders.registry import register

log = logging.getLogger("yahoo_loader")

_SYMBOL_MAP = {
    "XAUUSD": "GC=F",
    "BTCUSD": "BTC-USD",
    "GBPJPY": "GBPJPY=X",
}

_TF_MAP = {
    "M1":  "1m",  "M5":  "5m",  "M15": "15m",
    "M30": "30m", "H1":  "60m", "H4":  "4h",
    "D1":  "1d",
}

_HEADERS = {"User-Agent": "Mozilla/5.0"}


@register("yahoo", markets=["XAUUSD", "BTCUSD", "GBPJPY"])
def load_yahoo(symbol: str, timeframe: str, count: int = 200) -> pd.DataFrame:
    ticker = _SYMBOL_MAP.get(symbol.upper(), symbol)
    interval = _TF_MAP.get(timeframe.upper(), "5m")

    # range = enough to cover count bars (rough estimate)
    range_map = {"1m": "1d", "5m": "5d", "15m": "5d", "30m": "1mo",
                 "60m": "1mo", "4h": "3mo", "1d": "1y"}
    period = range_map.get(interval, "5d")

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"interval": interval, "range": period}

    resp = requests.get(url, params=params, headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    result = data["chart"]["result"][0]
    ts = result["timestamp"]
    q = result["indicators"]["quote"][0]

    df = pd.DataFrame({
        "time":   pd.to_datetime(ts, unit="s", utc=True),
        "open":   q["open"],
        "high":   q["high"],
        "low":    q["low"],
        "close":  q["close"],
        "volume": q.get("volume", [0.0] * len(ts)),
    })
    df.dropna(subset=["open", "close"], inplace=True)
    df = df.astype({"open": float, "high": float, "low": float,
                    "close": float, "volume": float})
    df.sort_values("time", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df.tail(count).reset_index(drop=True)
