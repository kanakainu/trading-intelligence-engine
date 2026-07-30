"""Test Phase 7.3 — Live Trading Runtime."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import MagicMock, patch
from adapters.broker.models import OrderResponse, AccountInfo

SETUPS = [{"id": "S001", "name": "LDN Bull", "requires": ["london", "bullish"]}]


@pytest.fixture
def live_runtime():
    with patch("adapters.broker.mt5_broker._get_gateway_client") as mock_broker_factory, \
         patch("adapters.market.mt5_market._get_gateway_client") as mock_market_factory:

        broker_client = MagicMock()
        broker_client.health.return_value = {"status": "ok"}
        broker_client.account.return_value = {
            "balance": 1000.0, "equity": 990.0, "margin": 10.0,
            "margin_free": 980.0, "margin_level": 9800.0, "currency": "USD", "leverage": 100
        }
        broker_client.buy.return_value = 12345
        mock_broker_factory.return_value = broker_client

        market_client = MagicMock()
        market_client.health.return_value = {"status": "ok"}
        market_client.price.return_value = {"bid": 2000.0, "ask": 2000.2, "spread": 20.0}
        mock_market_factory.return_value = market_client

        from runtime.live_trading import LiveTradingRuntime
        rt = LiveTradingRuntime(
            gateway_url="http://fake:8080",
            gateway_token="test-token",
            setup_definitions=SETUPS,
            symbols=["XAUUSD"],
        )
        rt.initialize()
        rt.start()
        yield rt, broker_client, market_client


def test_initialize_and_health(live_runtime):
    rt, broker, market = live_runtime
    h = rt.health()
    assert "broker" in h
    assert "market" in h
    assert h["running"] is True


def test_stop(live_runtime):
    rt, _, _ = live_runtime
    rt.stop()
    assert rt._running is False


def test_no_order_on_wait(live_runtime):
    rt, broker, market = live_runtime
    rt._market._ticks["XAUUSD"] = {
        "symbol": "XAUUSD", "bid": 2000.0, "ask": 2000.2, "spread": 20.0, "raw": {}
    }
    # Compiler returns WAIT (no setup match with empty context)
    rt._on_tick("XAUUSD", {})
    broker.buy.assert_not_called()


def test_live_runtime_no_trading_logic():
    import ast
    src = open("runtime/live_trading.py").read()
    tree = ast.parse(src)
    banned = {"decide", "rank_candidates", "ReasoningEngine", "SetupResolver"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in banned:
            pytest.fail(f"LiveTradingRuntime contains banned logic: {node.id}")
