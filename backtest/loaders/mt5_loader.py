"""MT5 loader — fetch historical OHLCV via MT5GatewayClient.candles().

Primary source for XAUUSD and GBPJPY.
ponytail: support date_range param when gateway supports /candles?from=&to=
"""
from __future__ import annotations
import sys
import logging
import pandas as pd
from datetime import timezone

sys.path.insert(0, '/home/ubuntu/.hermes/trading')
sys.path.insert(0, '/home/ubuntu/trading-intelligence-engine')

from gateway_client import MT5GatewayClient
from config.live import GATEWAY_URL, GATEWAY_TOKEN
from backtest.loaders.registry import register

log = logging.getLogger("mt5_loader")

_client: MT5GatewayClient | None = None

def _get_client() -> MT5GatewayClient:
    global _client
    if _client is None:
        _client = MT5GatewayClient(GATEWAY_URL, GATEWAY_TOKEN, timeout=10)
    return _client


@register("mt5", markets=["XAUUSD", "BTCUSD", "GBPJPY"])
def load_mt5(symbol: str, timeframe: str, count: int = 200) -> pd.DataFrame:
    """Fetch `count` bars from MT5 gateway. Returns OHLCV DataFrame UTC."""
    client = _get_client()
    raw = client.candles(symbol.upper(), timeframe, count)
    if not raw:
        raise ValueError(f"MT5 returned empty candles for {symbol}/{timeframe}")

    df = pd.DataFrame(raw)

    # Normalize column names (gateway may return time/open/high/low/close/tick_volume)
    rename = {
        "tick_volume": "volume",
        "real_volume": "volume",
        "vol": "volume",
    }
    df.rename(columns={k: v for k, v in rename.items() if k in df.columns}, inplace=True)

    # Ensure required columns
    required = ["time", "open", "high", "low", "close"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"MT5 candle missing column '{col}'. Got: {list(df.columns)}")

    if "volume" not in df.columns:
        df["volume"] = 0.0

    # Parse time → UTC datetime
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)

    df = df[["time", "open", "high", "low", "close", "volume"]].copy()
    df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})
    df.sort_values("time", inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df
