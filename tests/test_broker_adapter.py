"""Test Phase 4.2 — Broker Adapter."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from adapters.broker.base import BrokerAdapterBase
from adapters.broker.models import OrderRequest, OrderResponse, Position, AccountInfo
from adapters.broker.registry import BrokerRegistry
from adapters.broker.mock_broker import MockBrokerAdapter
from adapters.broker.exceptions import (
    BrokerConnectionError, OrderRejectedError, SymbolNotFoundError
)

@pytest.fixture
def mock():
    m = MockBrokerAdapter()
    m.initialize()
    m.connect()
    return m

@pytest.fixture
def reg():
    r = BrokerRegistry()
    r.register("mock", MockBrokerAdapter)
    return r

# ── connection ─────────────────────────────────────────────────────────────
def test_connect_success(mock):          assert mock.get_status().value == "CONNECTED"
def test_disconnect(mock):
    mock.disconnect();                  assert mock.get_status().value == "DISCONNECTED"
def test_initialize_state():
    m = MockBrokerAdapter()
    m.initialize();                     assert m.get_status().value == "INITIALIZED"

# ── account ────────────────────────────────────────────────────────────────
def test_get_balance(mock):             assert mock.get_balance() == 10000.0
def test_get_equity(mock):              assert mock.get_equity() == 10000.0
def test_account_info(mock):
    ai = mock.get_account_info()
    assert ai.balance == 10000.0 and ai.currency == "USD"

# ── market ─────────────────────────────────────────────────────────────────
def test_symbol_info(mock):
    si = mock.get_symbol_info("XAUUSD"); assert si["symbol"] == "XAUUSD"
def test_symbol_not_found(mock):
    with pytest.raises(SymbolNotFoundError): mock.get_symbol_info("FAKE")
def test_get_spread(mock):              assert mock.get_spread("XAUUSD") == 20.0

# ── order ──────────────────────────────────────────────────────────────────
def test_market_order(mock):
    req = OrderRequest(symbol="XAUUSD", side="BUY", volume=0.1)
    res = mock.submit_order(req)
    assert res.status == "FILLED" and res.filled_price > 0

def test_rejected_volume(mock):
    req = OrderRequest(symbol="XAUUSD", side="BUY", volume=0.001)
    res = mock.submit_order(req)
    assert res.status == "REJECTED"

def test_invalid_side(mock):
    req = OrderRequest(symbol="XAUUSD", side="FIRE", volume=0.1)
    res = mock.submit_order(req)
    assert res.status == "REJECTED"

def test_modify_order(mock):
    assert mock.modify_order("ord_0001").status == "MODIFIED"

def test_cancel_order(mock):            assert mock.cancel_order("ord_0001") is True

# ── position ───────────────────────────────────────────────────────────────
def test_open_position(mock):
    req = OrderRequest(symbol="XAUUSD", side="BUY", volume=0.1)
    mock.submit_order(req)
    pos = mock.get_positions()
    assert len(pos) >= 1

def test_close_position(mock):
    req = OrderRequest(symbol="XAUUSD", side="SELL", volume=0.5)
    mock.submit_order(req)
    pos = mock.get_positions()
    res = mock.close_position(pos[0].position_id)
    assert res.status == "CLOSED"

def test_get_orders(mock):
    mock.submit_order(OrderRequest(symbol="XAUUSD", side="BUY", volume=0.1))
    assert len(mock.get_orders()) >= 1

# ── registry ───────────────────────────────────────────────────────────────
def test_registry_register(reg):        assert reg.exists("mock")
def test_registry_load(reg):            assert isinstance(reg.load("mock"), MockBrokerAdapter)
def test_registry_list(reg):            assert "mock" in reg.list()

# ── no phase 3 touch ──────────────────────────────────────────────────────
def test_phase3_frozen():
    from core.execution.execution_contract import ExecutionContract
    from core.decision.decision_pipeline import DecisionPipeline
    assert DecisionPipeline
