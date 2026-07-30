"""Sprint 5.9 — Performance: measure pipeline latency per stage."""
import sys, os, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import statistics, pytest
from datetime import datetime, timezone
from core.context.context_model import MarketContext, Trend, Session, Volatility, MarketStatus
from core.facts.fact_compiler import FactCompiler
from core.setup.setup_resolver import SetupResolver
from core.decision.decision_pipeline import DecisionPipeline
from runtime.compiler_bridge import CompilerBridge
from runtime.context_builder import ExecutionContext

TS = datetime(2026, 7, 30, 10, 0, 0, tzinfo=timezone.utc)
SETUPS = [{"id": "S001", "name": "LDN Bull", "requires": ["london", "bullish"]}]

def bench(fn, n=50):
    times = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t) * 1000)
    return {
        "min":  round(min(times), 3),
        "max":  round(max(times), 3),
        "avg":  round(statistics.mean(times), 3),
        "p95":  round(sorted(times)[int(n * 0.95)], 3),
    }


def test_fact_compiler_latency(capsys):
    mc = MarketContext("XAUUSD", TS, trend=Trend.BULLISH, session=Session.LONDON,
                       atr=5.0, spread=20.0, volatility=Volatility.MEDIUM,
                       market_status=MarketStatus.OPEN)
    fc = FactCompiler()
    stats = bench(lambda: fc.compile(mc))
    with capsys.disabled(): print(f"\nFactCompiler: {stats}")
    assert stats["p95"] < 5.0, f"FactCompiler p95 {stats['p95']}ms too slow"


def test_setup_resolver_latency(capsys):
    sr = SetupResolver(SETUPS)
    stats = bench(lambda: sr.resolve({"london","bullish"}, set(), {"session":"london"}))
    with capsys.disabled(): print(f"SetupResolver: {stats}")
    assert stats["p95"] < 5.0, f"SetupResolver p95 {stats['p95']}ms too slow"


def test_decision_pipeline_latency(capsys):
    from core.setup.setup_match import SetupMatch
    dp = DecisionPipeline()
    m  = SetupMatch("S001", "LDN Bull", "READY", 0.9, ["london","bullish"], [])
    stats = bench(lambda: dp.decide([m], {}))
    with capsys.disabled(): print(f"DecisionPipeline: {stats}")
    assert stats["p95"] < 5.0, f"DecisionPipeline p95 {stats['p95']}ms too slow"


def test_full_pipeline_latency(capsys):
    bridge = CompilerBridge(SETUPS)
    snap   = {"symbol": "XAUUSD", "trend": "bullish", "session": "london",
              "atr": 5.0, "spread": 20.0, "market_status": "open", "timestamp": TS}
    stats = bench(lambda: bridge.compile(ExecutionContext(market=snap)))
    with capsys.disabled(): print(f"Full Pipeline:   {stats}")
    # Full pipeline under 20ms p95 is our SLA
    assert stats["p95"] < 20.0, f"Pipeline p95 {stats['p95']}ms exceeds 20ms SLA"
