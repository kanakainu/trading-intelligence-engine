"""Test Sprint 3.1 — Fact Compiler."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timezone
from core.context.context_model import MarketContext, Trend, Session, Volatility, MarketStatus
from core.facts.fact_compiler import FactCompiler
from core.facts.fact_compiler_set import TypedFactSet
from core.facts.typed_facts import TypedFact, TrendFact, SessionFact, StructureFact

def make_ctx(**kw):
    defaults = dict(symbol="XAUUSD", timestamp=datetime.now(timezone.utc),
                    trend=Trend.BULLISH, session=Session.LONDON,
                    atr=1.5, spread=20.0, volatility=Volatility.MEDIUM,
                    market_status=MarketStatus.OPEN)
    defaults.update(kw)
    return MarketContext(**defaults)

@pytest.fixture
def compiler(): return FactCompiler()

def test_compile_returns_factset(compiler):
    fs = compiler.compile(make_ctx())
    assert isinstance(fs, TypedFactSet)

def test_compile_trend_fact(compiler):
    fs = compiler.compile(make_ctx(trend=Trend.BULLISH))
    f = fs.find("trend")
    assert f and f.value == "bullish"

def test_compile_session_fact(compiler):
    fs = compiler.compile(make_ctx(session=Session.LONDON))
    f = fs.find("session")
    assert f and f.value == "london"

def test_compile_volatility_fact(compiler):
    fs = compiler.compile(make_ctx(volatility=Volatility.HIGH))
    facts = fs.find_by_type("MarketConditionFact")
    vals = [f.value for f in facts]
    assert "high" in vals

def test_compile_spread_fact(compiler):
    fs = compiler.compile(make_ctx(spread=500))
    f = fs.find("spread")
    assert f and f.value == "high"

def test_compile_multiple_facts(compiler):
    fs = compiler.compile(make_ctx())
    assert len(fs) >= 5

def test_factset_filter_by_type(compiler):
    fs = compiler.compile(make_ctx())
    mc_facts = fs.find_by_type("MarketConditionFact")
    assert len(mc_facts) >= 2

def test_factset_summary(compiler):
    fs = compiler.compile(make_ctx())
    s = fs.summary()
    assert "trend" in s and "session" in s

def test_empty_context_no_crash(compiler):
    ctx = make_ctx(atr=0.0, spread=0.0, market_status=MarketStatus.CLOSED)
    fs = compiler.compile(ctx)
    assert isinstance(fs, TypedFactSet)

def test_no_buy_sell_in_facts(compiler):
    fs = compiler.compile(make_ctx())
    for f in fs.filter(lambda x: True):
        assert f.value not in ("BUY","SELL","WAIT")
        assert "buy" not in str(f.value).lower().replace("bullish","")
        assert "sell" not in str(f.value).lower().replace("bearish","")
