"""DataPipeline — high-level API for loading OHLCV data.

Imports all loaders (registers them as side effect) then exposes
a single `load()` call. This is the entry point for backtest engine.

Usage:
    from backtest.pipeline import load
    df = load('XAUUSD', 'M5', 200)
"""
from __future__ import annotations
import logging

# Import loaders to trigger @register side effects
import backtest.loaders.mt5_loader      # noqa: F401
import backtest.loaders.yahoo_loader    # noqa: F401
import backtest.loaders.stooq_loader    # noqa: F401
import backtest.loaders.binance_loader  # noqa: F401

from backtest.loaders.registry import load  # re-export

log = logging.getLogger("DataPipeline")

__all__ = ["load"]


if __name__ == "__main__":
    # Smoke test — run: python3 -m backtest.pipeline
    import sys
    logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")

    tests = [
        ("XAUUSD", "M5",  50),
        ("BTCUSD", "M5",  50),
        ("GBPJPY", "M5",  50),
    ]

    ok = 0
    for sym, tf, n in tests:
        try:
            df = load(sym, tf, n)
            assert len(df) > 0, "empty"
            assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"]
            print(f"  PASS  {sym}/{tf} — {len(df)} bars, last={df['time'].iloc[-1]}")
            ok += 1
        except Exception as e:
            print(f"  FAIL  {sym}/{tf} — {e}")

    print(f"\n{ok}/{len(tests)} passed")
    sys.exit(0 if ok == len(tests) else 1)
