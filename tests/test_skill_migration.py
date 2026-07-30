"""Test Sprint 5.4 — Rule Plugin Framework."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.rules.plugins.plugin_interface import RuleResult
from core.rules.plugins.plugin_registry import PluginRegistry
from core.rules.plugins.plugin_loader import PluginLoader
from core.rules.plugins.news_filter import NewsFilterPlugin
from core.rules.plugins.dynamic_lot import DynamicLotPlugin
from core.rules.plugins.adaptive_drawdown import AdaptiveDrawdownPlugin
from core.rules.plugins.daily_target import DailyTargetPlugin


def make_plugin(cls, config=None):
    p = cls()
    p.initialize(config or {})
    return p


# ── NewsFilter ─────────────────────────────────────────────────────────────
def test_news_filter_clear():
    p = make_plugin(NewsFilterPlugin)
    r = p.evaluate({"news_events": []}, {})
    assert r.status == "APPROVE"

def test_news_filter_block_fomc():
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    p = make_plugin(NewsFilterPlugin)
    r = p.evaluate({"news_events": [{"title": "FOMC Meeting", "time": now}]}, {})
    assert r.status == "REJECT"
    assert "FOMC" in r.reason

def test_news_filter_disabled():
    p = make_plugin(NewsFilterPlugin, {"enabled": False})
    assert not p.enabled()


# ── DynamicLot ─────────────────────────────────────────────────────────────
def test_lot_approve():
    p = make_plugin(DynamicLotPlugin, {"min_lot": 0.01, "max_lot": 1.0})
    r = p.evaluate({"lot": 0.1}, {})
    assert r.status == "APPROVE"

def test_lot_reject_too_small():
    p = make_plugin(DynamicLotPlugin, {"min_lot": 0.05})
    r = p.evaluate({"lot": 0.01}, {})
    assert r.status == "REJECT"

def test_lot_reject_too_large():
    p = make_plugin(DynamicLotPlugin, {"max_lot": 0.5})
    r = p.evaluate({"lot": 1.0}, {})
    assert r.status == "REJECT"

def test_lot_reject_zero():
    p = make_plugin(DynamicLotPlugin)
    r = p.evaluate({"lot": 0}, {})
    assert r.status == "REJECT"


# ── AdaptiveDrawdown ────────────────────────────────────────────────────────
def test_drawdown_approve():
    p = make_plugin(AdaptiveDrawdownPlugin, {"limit_pct": 0.05})
    r = p.evaluate({"equity": 9800, "peak_balance": 10000}, {})
    assert r.status == "APPROVE"

def test_drawdown_reject():
    p = make_plugin(AdaptiveDrawdownPlugin, {"limit_pct": 0.05})
    r = p.evaluate({"equity": 9000, "peak_balance": 10000}, {})
    assert r.status == "REJECT"

def test_drawdown_no_peak():
    p = make_plugin(AdaptiveDrawdownPlugin)
    r = p.evaluate({"equity": 9000, "peak_balance": 0}, {})
    assert r.status == "APPROVE"  # no peak = no constraint


# ── DailyTarget ─────────────────────────────────────────────────────────────
def test_daily_target_approve():
    p = make_plugin(DailyTargetPlugin, {"target_usd": 30.0})
    r = p.evaluate({"daily_pnl": 20.0}, {})
    assert r.status == "APPROVE"

def test_daily_target_reject():
    p = make_plugin(DailyTargetPlugin, {"target_usd": 30.0})
    r = p.evaluate({"daily_pnl": 35.0}, {})
    assert r.status == "REJECT"


# ── Registry ────────────────────────────────────────────────────────────────
def test_registry_register_list():
    reg = PluginRegistry()
    reg.register("news", make_plugin(NewsFilterPlugin))
    assert "news" in reg.list_all()
    assert "news" in reg.list_enabled()


# ── PluginLoader ────────────────────────────────────────────────────────────
def test_loader_all_approve():
    reg = PluginRegistry()
    reg.register("lot", make_plugin(DynamicLotPlugin, {"min_lot": 0.01, "max_lot": 1.0}))
    reg.register("dd", make_plugin(AdaptiveDrawdownPlugin, {"limit_pct": 0.1}))
    loader = PluginLoader(reg)
    results = loader.run_all({"lot": 0.1, "equity": 9500, "peak_balance": 10000}, {})
    assert all(r.status == "APPROVE" for r in results)

def test_loader_short_circuit_on_reject():
    reg = PluginRegistry()
    reg.register("news", make_plugin(NewsFilterPlugin))
    # Lot with zero — will reject
    reg.register("lot", make_plugin(DynamicLotPlugin, {"min_lot": 0.01}))
    loader = PluginLoader(reg)
    results = loader.run_all({"lot": 0, "news_events": []}, {})
    # Should stop at lot reject
    assert any(r.status == "REJECT" for r in results)

def test_priority_order():
    news = make_plugin(NewsFilterPlugin)   # priority 10
    lot = make_plugin(DynamicLotPlugin)    # priority 20
    dd = make_plugin(AdaptiveDrawdownPlugin) # priority 30
    assert news.priority() < lot.priority() < dd.priority()
