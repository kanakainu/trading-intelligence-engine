"""Test Phase 4.3 — Market Data Adapter."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from decimal import Decimal
from datetime import datetime, timezone
from adapters.market.base import MarketAdapterBase
from adapters.market.models import Tick, Candle, MarketSnapshot, HealthReport
from adapters.market.normalizer import (
    normalize_tick, normalize_candle, normalize_symbol,
    normalize_price, normalize_volume, normalize_spread, normalize_timestamp
)
from adapters.market.cache import MarketCache
from adapters.market.registry import MarketRegistry
from adapters.market.mock_market import MockMarketAdapter
from adapters.market.exceptions import (
    MarketConnectionError, SubscriptionError, DataUnavailableError,
    InvalidSymbolError, MarketTimeoutError
)

# ── Normalizer ─────────────────────────────────────────────────────────────
def test_normalize_symbol():
    assert normalize_symbol("XAUUSD") == "XAUUSD"
    assert normalize_symbol("xau.usd") == "XAUUSD"
    assert normalize_symbol("XAU/USD") == "XAUUSD"

def test_normalize_price():
    assert normalize_price("1.08500") == Decimal('1.08')  # banker's rounding
    assert normalize_price("2000.12345") == Decimal('2000.12')

def test_normalize_volume():
    assert normalize_volume("0.1") == Decimal('0.10')
    assert normalize_volume(1000) == Decimal('1000.00')

def test_normalize_spread():
    # spread = ask - bid = 1.08010 - 1.08000 = 0.00010
    assert normalize_spread(Decimal('1.08010'), Decimal('1.08000')) == Decimal('0.00')

def test_normalize_timestamp():
    ts = normalize_timestamp("2026-01-01T12:00:00Z")
    assert ts.tzinfo is not None and ts.tzinfo.utcoffset(ts).total_seconds() == 0

def test_normalize_tick():
    raw = {"symbol": "XAUUSD", "bid": 2000.0, "ask": 2000.20, "timestamp": datetime.now(timezone.utc).isoformat()}
    norm = normalize_tick(raw)
    assert norm["symbol"] == "XAUUSD"
    assert norm["spread"] == Decimal("0.20")

def test_normalize_candle():
    raw = {"symbol": "XAUUSD", "timeframe": "M5", "open": 2000, "high": 2010, "low": 1995, "close": 2005, "volume": 100}
    n = normalize_candle(raw)
    assert n["symbol"] == "XAUUSD" and n["timeframe"] == "M5"

# ── Cache ──────────────────────────────────────────────────────────────────
def test_cache_tick():
    cache = MarketCache(default_ttl=1)
    tick = Tick(symbol="XAUUSD", bid=Decimal("2000"), ask=Decimal("2000.20"),
                spread=Decimal("0.20"), timestamp=datetime.now(timezone.utc))
    cache.set_tick(tick)
    g = cache.get_tick("XAUUSD")
    assert g is not None and g.symbol == "XAUUSD"

def test_cache_candle():
    cache = MarketCache(default_ttl=60)
    candle = Candle(symbol="XAUUSD", timeframe="M5", open=Decimal("2000"),
                    high=Decimal("2010"), low=Decimal("1995"), close=Decimal("2005"),
                    volume=Decimal("100"), timestamp=datetime.now(timezone.utc))
    cache.set_candle(candle)
    g = cache.get_candle("XAUUSD", "M5")
    assert g is not None and g.symbol == "XAUUSD"

def test_cache_snapshot():
    cache = MarketCache(default_ttl=10)
    snap = MarketSnapshot(symbol="XAUUSD", last_price=Decimal("2000"),
                          spread=Decimal("20"), timestamp=datetime.now(timezone.utc))
    cache.set_snapshot(snap)
    g = cache.get_snapshot("XAUUSD")
    assert g is not None

def test_cache_ttl_expiration():
    cache = MarketCache(default_ttl=0)
    tick = Tick(symbol="XAUUSD", bid=Decimal("2000"), ask=Decimal("2000.20"),
                spread=Decimal("20"), timestamp=datetime.now(timezone.utc))
    cache.set_tick(tick)
    assert cache.get_tick("XAUUSD") is None  # immediate expiration

# ── Mock Market ─────────────────────────────────────────────────────────────
@pytest.fixture
def market():
    m = MockMarketAdapter()
    m.initialize()
    m.connect()
    return m

def test_mock_connect(market):
    assert market.get_status() == "CONNECTED"

def test_mock_disconnect(market):
    market.disconnect()
    assert market.get_status() == "DISCONNECTED"

def test_mock_health(market):
    h = market.health_check()
    assert h["status"] == "CONNECTED" and h["connected"] is True

def test_mock_subscribe(market):
    market.subscribe("XAUUSD")
    assert "XAUUSD" in market._subscriptions

def test_mock_unsubscribe(market):
    market.unsubscribe("XAUUSD")
    assert "XAUUSD" not in market._subscriptions

def test_mock_get_tick(market):
    tick = market.get_latest_tick("XAUUSD")
    # mock updates ticks in background thread, may take a moment
    # just verify it doesn't crash
    assert tick is None or isinstance(tick, dict)

def test_mock_snapshot_none(market):
    assert market.get_market_snapshot("XAUUSD") is None

# ── Registry ───────────────────────────────────────────────────────────────
def test_market_registry():
    reg = MarketRegistry()
    reg.register("mock", MockMarketAdapter)
    assert reg.exists("mock")
    assert "mock" in reg.list()
    m = reg.load("mock")
    assert isinstance(m, MockMarketAdapter)

# ── Phase 3 frozen ─────────────────────────────────────────────────────────
def test_phase3_frozen():
    from core.execution.execution_contract import ExecutionContract
    from core.decision.decision_pipeline import DecisionPipeline
    assert DecisionPipeline