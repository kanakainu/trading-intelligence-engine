"""Test Phase 7.2 — MT5 Market Adapter."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal
from datetime import datetime, timezone

with patch.dict("sys.modules", {"gateway_client": MagicMock()}):
    sys.path.insert(0, "/home/ubuntu/.hermes/trading")
    from adapters.market.mt5_market import MT5MarketAdapter
    from adapters.market.models import Tick, Candle, MarketSnapshot


@pytest.fixture
def adapter():
    fake_gateway = MagicMock()
    fake_gateway.MT5GatewayClient.return_value.health.return_value = {"status": "ok"}
    fake_gateway.MT5GatewayClient.return_value.price.return_value = {
        "bid": 2000.0, "ask": 2000.2, "spread": 20.0, "volume": 100
    }
    fake_gateway.MT5GatewayClient.return_value.candles.return_value = [{
        "open": 1998.0, "high": 2001.0, "low": 1997.0, "close": 2000.0,
        "volume": 100, "time": "2026-07-30T10:00:00Z"
    }]
    fake_gateway.MT5GatewayClient.return_value.health.return_value = {"status": "ok"}

    with patch.dict("sys.modules", {"gateway_client": MagicMock()}):
        from adapters.market.mt5_market import MT5MarketAdapter
        a = MT5MarketAdapter("http://fake:8080", "test-token", poll_interval=0.01)
        a.initialize()
        a.connect()
        # Patch the client directly on the adapter instance
        a._client = MagicMock()
        a._client.price.return_value = {"bid": 2000.0, "ask": 2000.2, "spread": 20.0, "volume": 100}
        a._client.candles.return_value = [{
            "open": 1998.0, "high": 2001.0, "low": 1997.0, "close": 2000.0,
            "volume": 100, "time": "2026-07-30T10:00:00Z"
        }]
        a._client.health.return_value = {"status": "ok"}
        yield a


def test_initialize_and_health(adapter):
    a = adapter
    assert a.name == "mt5_market"
    h = a.health_check()
    assert h["status"] == "CONNECTED"


def test_subscribe_and_get_tick(adapter):
    a = adapter
    a.subscribe("XAUUSD")
    a._client.price.return_value = {"bid": 2001.0, "ask": 2001.2, "spread": 20.0, "volume": 50}
    a._client.candles.return_value = [{"open": 2000.0, "high": 2005.0, "low": 1995.0, "close": 2002.0, "volume": 200, "time": "2026-07-30T10:01:00Z"}]
    # Wait for poll loop
    import time
    time.sleep(0.05)

    tick = a.get_latest_tick("XAUUSD")
    assert isinstance(tick, Tick)
    assert tick.symbol == "XAUUSD"
    assert tick.bid > 0
    assert tick.spread > 0


def test_get_latest_candle(adapter):
    a = adapter
    a._candles["XAUUSD"] = [{
        "open": 1998.0, "high": 2001.0, "low": 1997.0, "close": 2000.0,
        "volume": 100, "time": "2026-07-30T10:00:00Z"
    }]
    candle = a.get_latest_candle("XAUUSD", "M5")
    assert isinstance(candle, Candle)
    assert candle.symbol == "XAUUSD"
    assert candle.timeframe == "M5"
    assert candle.close > 0


def test_get_market_snapshot(adapter):
    a = adapter
    a._ticks["XAUUSD"] = {
        "symbol": "XAUUSD", "bid": 2000.0, "ask": 2000.2,
        "spread": 20.0, "volume": 100, "timestamp": "now",
        "raw": {"bid": 2000.0, "ask": 2000.2},
    }
    snap = a.get_market_snapshot("XAUUSD")
    assert isinstance(snap, MarketSnapshot)
    assert snap.symbol == "XAUUSD"
    assert snap.last_price > 0
    assert snap.spread > 0


def test_unsubscribe(adapter):
    a = adapter
    a.unsubscribe("XAUUSD")
    # Verify cleanup
    assert "XAUUSD" not in a._subscribed


def test_no_trading_logic_in_market_adapter():
    import ast
    src = open("adapters/market/mt5_market.py").read()
    tree = ast.parse(src)
    banned = {"submit_order", "buy", "sell", "close_position", "modify_order", "order"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in banned:
                pytest.fail(f"Found banned call: {node.func.id}")
        if isinstance(node, ast.Attribute) and node.attr in banned:
            pytest.fail(f"Found banned attr: {node.attr}")