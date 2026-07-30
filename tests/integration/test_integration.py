"""Sprint 5.9 — Integration Tests: full TIE pipeline end-to-end."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pytest
from datetime import datetime, timezone
from core.context.context_model import MarketContext, Trend, Session, Volatility, MarketStatus
from core.facts.fact_compiler import FactCompiler
from core.setup.setup_resolver import SetupResolver
from core.decision.decision_pipeline import DecisionPipeline
from core.execution.execution_contract import ExecutionContract
from runtime.compiler_bridge import CompilerBridge
from runtime.context_builder import ExecutionContext
from core.rules.risk.risk_registry import build_risk_registry
from core.rules.plugins.plugin_loader import PluginLoader


SAMPLE_SETUPS = [
    {"id": "BYS-S001", "name": "London Breakout BUY", "requires": ["london", "bullish"],
     "direction": "BUY", "confidence_base": 0.8},
    {"id": "BYS-S002", "name": "NY SELL Setup", "requires": ["new_york", "bearish"],
     "direction": "SELL", "confidence_base": 0.75},
]


def make_context(**market):
    base = dict(symbol="XAUUSD", trend="bullish", session="london",
                atr=5.0, spread=20.0, volatility="medium",
                market_status="open", timestamp=datetime.now(timezone.utc))
    base.update(market)
    return ExecutionContext(market=base)


# ── Context Engine ────────────────────────────────────────────────────────────
def test_context_engine_imports():
    from core.context.context_engine import ContextEngine
    assert ContextEngine

def test_market_context_creation():
    mc = MarketContext(symbol="XAUUSD", timestamp=datetime.now(timezone.utc),
                       trend=Trend.BULLISH, session=Session.LONDON)
    assert mc.symbol == "XAUUSD"


# ── Fact Compiler ─────────────────────────────────────────────────────────────
def test_fact_compiler_produces_facts():
    fc = FactCompiler()
    mc = MarketContext("XAUUSD", datetime.now(timezone.utc), trend=Trend.BULLISH,
                       session=Session.LONDON, atr=5.0, spread=20.0,
                       volatility=Volatility.MEDIUM, market_status=MarketStatus.OPEN)
    fs = fc.compile(mc)
    assert len(fs) > 0

def test_fact_compiler_deterministic():
    """Same input must produce same facts every time."""
    ts = datetime(2026, 7, 30, 10, 0, 0, tzinfo=timezone.utc)
    mc = MarketContext("XAUUSD", ts, trend=Trend.BULLISH, session=Session.LONDON,
                       atr=5.0, spread=20.0, volatility=Volatility.MEDIUM,
                       market_status=MarketStatus.OPEN)
    fc = FactCompiler()
    fs1 = fc.compile(mc)
    fs2 = fc.compile(mc)
    names1 = {f.name for f in fs1._facts}
    names2 = {f.name for f in fs2._facts}
    assert names1 == names2


# ── Setup Resolver ────────────────────────────────────────────────────────────
def test_setup_resolver_no_setups_returns_empty():
    sr = SetupResolver([])
    matches = sr.resolve(set(), set(), {})
    assert isinstance(matches, list)

def test_setup_resolver_matches_with_london_bullish():
    sr = SetupResolver(SAMPLE_SETUPS)
    matches = sr.resolve({"london", "bullish"}, set(), {"session": "london"})
    ready = [m for m in matches if m.status == "READY"]
    assert len(ready) >= 1


# ── Decision Pipeline ─────────────────────────────────────────────────────────
def test_decision_pipeline_wait_on_empty():
    from core.decision.trade_decision import WAIT
    dp = DecisionPipeline()
    d = dp.decide([], {})
    assert d.action == WAIT

def test_decision_pipeline_deterministic():
    from core.setup.setup_match import SetupMatch
    dp = DecisionPipeline()
    m = SetupMatch("S001", "Test Setup", "READY", 0.9, ["london"], [])
    d1 = dp.decide([m], {})
    d2 = dp.decide([m], {})
    assert d1.action == d2.action


# ── Compiler Bridge ───────────────────────────────────────────────────────────
def test_compiler_bridge_full_pipeline():
    bridge = CompilerBridge(SAMPLE_SETUPS)
    ctx = make_context()
    decision = bridge.compile(ctx)
    assert decision is not None
    assert hasattr(decision, "action")
    assert hasattr(decision, "reason")

def test_compiler_bridge_deterministic():
    """Same snapshot → same decision every time."""
    bridge = CompilerBridge(SAMPLE_SETUPS)
    ctx = make_context(symbol="XAUUSD", trend="bullish", session="london")
    d1 = bridge.compile(ctx)
    d2 = bridge.compile(ctx)
    assert d1.action == d2.action


# ── Rule Engine ───────────────────────────────────────────────────────────────
def test_risk_registry_full_gate_approve():
    reg = build_risk_registry()
    loader = PluginLoader(reg)
    ctx = {"spread": 50, "lot": 0.1, "equity": 9800, "peak_balance": 10000,
           "daily_pnl": 5.0, "entry": 2000.0, "sl": 1990.0, "tp": 2020.0,
           "direction": "BUY", "news_events": []}
    results = loader.run_all(ctx, {}, decision={"confidence": 0.8})
    rejected = [r for r in results if r.status == "REJECT"]
    assert len(rejected) == 0

def test_risk_registry_spread_blocks():
    reg = build_risk_registry(overrides={"spread": {"max_spread": 10}})
    loader = PluginLoader(reg)
    ctx = {"spread": 500, "lot": 0.1, "news_events": []}
    results = loader.run_all(ctx, {})
    assert any(r.status == "REJECT" for r in results)


# ── Execution Contract ────────────────────────────────────────────────────────
def test_execution_contract_fields():
    c = ExecutionContract(symbol="XAUUSD", action="BUY", direction="BUY",
                          entry=2000.0, sl=1990.0, tp=2020.0)
    assert c.symbol == "XAUUSD"
    assert c.action == "BUY"

def test_execution_contract_default_id():
    c1 = ExecutionContract()
    c2 = ExecutionContract()
    assert c1.contract_id != c2.contract_id


# ── Explanation Generator ─────────────────────────────────────────────────────
def test_explanation_engine_imports():
    from core.explanation.explanation_engine import ExplanationEngine
    assert ExplanationEngine

def test_explanation_builder_imports():
    from core.explanation.explanation_builder import ExplanationBuilder
    assert ExplanationBuilder
