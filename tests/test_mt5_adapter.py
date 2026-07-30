"""Test Phase 7.1 — MT5 Broker Adapter."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import MagicMock, patch
from adapters.broker.models import OrderRequest, AccountInfo


@pytest.fixture
def adapter():
    from adapters.broker.mt5_broker import MT5BrokerAdapter as MT5
    with patch("adapters.broker.mt5_broker._get_gateway_client") as mock_factory:
        client = MagicMock()
        client.health.return_value = {"status": "ok"}
        mock_factory.return_value = client
        a = MT5("http://fake:8080", "test-token")
        a.initialize()
        a.connect()
        yield a, client


def test_health_check(adapter):
    a, _ = adapter
    h = a.health_check()
    assert isinstance(h, dict)


def test_get_account_info(adapter):
    a, client = adapter
    client.account.return_value = {
        "balance": 10000.0, "equity": 9500.0, "margin": 500.0,
        "margin_free": 9000.0, "margin_level": 2000.0,
        "currency": "USD", "leverage": 100,
    }
    info = a.get_account_info()
    assert isinstance(info, AccountInfo)
    assert info.balance == 10000.0
    assert info.currency == "USD"


def test_submit_buy_order(adapter):
    a, client = adapter
    client.buy.return_value = 12345
    req = OrderRequest(symbol="XAUUSD", side="BUY", volume=0.1)
    resp = a.submit_order(req)
    assert resp.status == "FILLED"
    assert resp.order_id == "12345"
    client.buy.assert_called_once()


def test_submit_sell_order(adapter):
    a, client = adapter
    client.sell.return_value = 12346
    req = OrderRequest(symbol="EURUSD", side="SELL", volume=0.2)
    resp = a.submit_order(req)
    assert resp.status == "FILLED"
    client.sell.assert_called_once()


def test_submit_order_rejected(adapter):
    a, client = adapter
    client.buy.return_value = None
    req = OrderRequest(symbol="XAUUSD", side="BUY", volume=0.1)
    resp = a.submit_order(req)
    assert resp.status == "REJECTED"


def test_get_positions(adapter):
    a, client = adapter
    client.positions.return_value = [
        {"ticket": 1001, "symbol": "XAUUSD", "direction": "buy",
         "volume": 0.1, "open_price": 2000.0, "sl": 1990.0, "tp": 2020.0, "profit": 50.0}
    ]
    positions = a.get_positions()
    assert len(positions) == 1
    assert positions[0].position_id == "1001"
    assert positions[0].side == "BUY"


def test_close_position(adapter):
    a, client = adapter
    client.close.return_value = True
    resp = a.close_position("1001")
    assert resp.status == "FILLED"


def test_modify_order(adapter):
    a, client = adapter
    client.modify.return_value = {"success": True}
    resp = a.modify_order("1001", stop_loss=1995.0, take_profit=2025.0)
    assert resp.status == "FILLED"


def test_name(adapter):
    a, _ = adapter
    assert a.name == "mt5_broker"


def test_no_trading_logic_in_adapter():
    import ast
    src = open("adapters/broker/mt5_broker.py").read()
    tree = ast.parse(src)
    # adapter should not import decision/setup/facts
    banned_imports = {"decision_pipeline", "setup_resolver", "fact_compiler"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = getattr(node, 'module', '') or ''
            for b in banned_imports:
                assert b not in mod
