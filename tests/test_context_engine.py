import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timezone
from core.context.context_model import Trend, Session, Volatility, MarketStatus
from core.context.context_engine import ContextEngine
from core.context.context_registry import ContextRegistry


def candles(prices):
    return [{"open": p, "high": p+1, "low": p-1, "close": p, "volume": 100} for p in prices]

@pytest.fixture
def engine():
    return ContextEngine()

def test_trend_bullish(engine):
    data = {"symbol": "X", "timestamp": datetime.now(timezone.utc),
            "candles": candles([100, 101, 102, 103, 104, 105, 106, 107, 108, 109])}
    ctx = engine.build(data)
    assert ctx.trend == Trend.BULLISH

def test_trend_bearish(engine):
    data = {"symbol": "X", "timestamp": datetime.now(timezone.utc),
            "candles": candles([109, 108, 107, 106, 105, 104, 103, 102, 101, 100])}
    ctx = engine.build(data)
    assert ctx.trend == Trend.BEARISH

def test_trend_sideways(engine):
    data = {"symbol": "X", "timestamp": datetime.now(timezone.utc),
            "candles": candles([100]*10)}
    ctx = engine.build(data)
    assert ctx.trend == Trend.SIDEWAYS

def test_trend_unknown_few_candles(engine):
    data = {"symbol": "X", "timestamp": datetime.now(timezone.utc), "candles": []}
    ctx = engine.build(data)
    assert ctx.trend == Trend.UNKNOWN

def test_atr_calculated(engine):
    c = candles([100]*15)
    data = {"symbol": "X", "timestamp": datetime.now(timezone.utc), "candles": c}
    ctx = engine.build(data)
    assert ctx.atr > 0

def test_session_london(engine):
    ts = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)  # 09:00 UTC = London only
    data = {"symbol": "X", "timestamp": ts, "candles": candles([100]*5)}
    ctx = engine.build(data)
    assert ctx.session == Session.LONDON

def test_session_overlap(engine):
    ts = datetime(2026, 1, 1, 13, 0, tzinfo=timezone.utc)  # 13:00 UTC = London+NY
    data = {"symbol": "X", "timestamp": ts, "candles": candles([100]*5)}
    ctx = engine.build(data)
    assert ctx.session == Session.OVERLAP

def test_session_asia(engine):
    ts = datetime(2026, 1, 1, 3, 0, tzinfo=timezone.utc)
    data = {"symbol": "X", "timestamp": ts, "candles": candles([100]*5)}
    ctx = engine.build(data)
    assert ctx.session == Session.ASIA

def test_market_status_closed(engine):
    data = {"symbol": "X", "timestamp": datetime.now(timezone.utc),
            "candles": [], "market_open": False}
    ctx = engine.build(data)
    assert ctx.market_status == MarketStatus.CLOSED

def test_spread_passed(engine):
    data = {"symbol": "X", "timestamp": datetime.now(timezone.utc),
            "candles": [], "spread": 25.5}
    ctx = engine.build(data)
    assert ctx.spread == 25.5

def test_context_registry():
    reg = ContextRegistry()
    engine = ContextEngine()
    data = {"symbol": "XAUUSD", "timestamp": datetime.now(timezone.utc), "candles": []}
    ctx = engine.build(data)
    reg.update(ctx)
    assert reg.get("XAUUSD") is not None
    assert reg.get("UNKNOWN") is None
    reg.clear("XAUUSD")
    assert reg.get("XAUUSD") is None

def test_no_trading_logic_in_context():
    """Context must never contain trading action keywords in actual code (not comments/docstrings)."""
    import ast, core.context.context_engine as ce, inspect
    src = inspect.getsource(ce)
    tree = ast.parse(src)
    # Check only code (not docstrings/comments) for forbidden patterns
    forbidden_calls = ["BUY", "SELL", "WAIT", "RBR", "SNRC", "order_block"]
    for node in ast.walk(tree):
        if isinstance(node, (ast.Name, ast.Attribute)):
            name = node.id if isinstance(node, ast.Name) else node.attr
            for f in forbidden_calls:
                assert f not in name, f"Trading logic found in code: {f}"
