"""Stooq loader — pure requests, CSV endpoint.

Fallback for GBPJPY.
ponytail: add more symbol mappings when needed.
"""
from __future__ import annotations
import io
import logging
import requests
import pandas as pd
from backtest.loaders.registry import register

log = logging.getLogger("stooq_loader")

_SYMBOL_MAP = {
    "GBPJPY": "gbpjpy",
    "XAUUSD": "xauusd",
    "BTCUSD": "btcusd",
}

_TF_MAP = {
    "M1": "1", "M5": "5", "M15": "15", "M30": "30",
    "H1": "60", "H4": "240", "D1": "d",
}


@register("stooq", markets=["GBPJPY", "XAUUSD"])
def load_stooq(symbol: str, timeframe: str, count: int = 200) -> pd.DataFrame:
    ticker = _SYMBOL_MAP.get(symbol.upper(), symbol.lower())
    interval = _TF_MAP.get(timeframe.upper(), "5")

    url = f"https://stooq.com/q/d/l/?s={ticker}&i={interval}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()

    df = pd.read_csv(io.StringIO(resp.text))
    df.columns = [c.lower() for c in df.columns]

    rename = {"date": "time", "vol": "volume", "volume": "volume"}
    df.rename(columns=rename, inplace=True)

    if "time" not in df.columns:
        raise ValueError(f"Stooq CSV missing 'date' column. Got: {list(df.columns)}")

    df["time"] = pd.to_datetime(df["time"], utc=True)
    if "volume" not in df.columns:
        df["volume"] = 0.0

    df = df[["time", "open", "high", "low", "close", "volume"]].copy()
    df = df.astype({"open": float, "high": float, "low": float,
                    "close": float, "volume": float})
    df.dropna(subset=["open", "close"], inplace=True)
    df.sort_values("time", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df.tail(count).reset_index(drop=True)
