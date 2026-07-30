"""Test Sprint 6.4 — Context Injection."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import MagicMock
from core.context.immutable_context import ImmutableContext
from core.context.context_cache import ContextCache
from core.context.context_validator import ContextValidator
from core.context.context_injector import ContextInjector


def mock_hck(identity=None, goals=None, semantic=None, episodes=None):
    h = MagicMock()
    h.get_identity.return_value = {"name": "Boskuh", "lid": "boskuh"} if identity is None else identity
    h.get_goals.return_value = [{"category": "goal", "content": "earn $30/day"}] if goals is None else goals
    h.get_semantic_memory.return_value = [{"category": "fact", "content": "trend bullish"}] if semantic is None else semantic
    h.get_recent_episodes.return_value = [{"role": "user", "content": "buy signal"}] if episodes is None else episodes
    return h


# ── ImmutableContext ──────────────────────────────────────────────────────
def test_immutable_context_frozen():
    ctx = ImmutableContext(
        identity={"name": "Boskuh"},
        goals=({"category": "goal"},),
        semantic_memory=({"content": "bullish"},),
        recent_episodes=({"role": "user"},),
        recent_reflections=(),
        active_session="london",
        metadata={},
        canonical_id="boskuh",
    )
    with pytest.raises((AttributeError, TypeError)):
        ctx.canonical_id = "changed"  # must be frozen

def test_immutable_to_dict():
    ctx = ImmutableContext(
        identity={"name": "x"}, goals=(), semantic_memory=(),
        recent_episodes=(), recent_reflections=(),
        active_session="s1", metadata={}, canonical_id="x",
    )
    d = ctx.to_dict()
    assert d["canonical_id"] == "x"
    assert isinstance(d["goals"], list)


# ── ContextCache ──────────────────────────────────────────────────────────
def test_cache_miss_on_different_session():
    cache = ContextCache()
    ctx = ImmutableContext(identity={}, goals=(), semantic_memory=(),
                           recent_episodes=(), recent_reflections=(),
                           active_session="s1", metadata={}, canonical_id="x")
    cache.set("s1", ctx)
    assert cache.get("s2") is None  # different session

def test_cache_hit_same_session():
    cache = ContextCache()
    ctx = ImmutableContext(identity={}, goals=(), semantic_memory=(),
                           recent_episodes=(), recent_reflections=(),
                           active_session="s1", metadata={}, canonical_id="x")
    cache.set("s1", ctx)
    assert cache.get("s1") is ctx

def test_cache_invalidate():
    cache = ContextCache()
    ctx = ImmutableContext(identity={}, goals=(), semantic_memory=(),
                           recent_episodes=(), recent_reflections=(),
                           active_session="s1", metadata={}, canonical_id="x")
    cache.set("s1", ctx)
    cache.invalidate()
    assert cache.get("s1") is None


# ── ContextValidator ──────────────────────────────────────────────────────
def test_validator_full_context():
    ctx = ImmutableContext(
        identity={"name": "B"}, goals=({"g": 1},),
        semantic_memory=({"s": 1},), recent_episodes=({"e": 1},),
        recent_reflections=({"r": 1},),
        active_session="s1", metadata={}, canonical_id="x")
    v = ContextValidator()
    checks = v.validate(ctx)
    assert all(checks.values())

def test_validator_empty_context():
    ctx = ImmutableContext(identity={}, goals=(), semantic_memory=(),
                           recent_episodes=(), recent_reflections=(),
                           active_session="", metadata={}, canonical_id="x")
    v = ContextValidator()
    assert v.is_healthy(ctx) is False  # no identity


# ── ContextInjector ───────────────────────────────────────────────────────
def test_injector_builds_context():
    hck = mock_hck()
    inj = ContextInjector(hck)
    ctx = inj.inject("boskuh", "london")
    assert isinstance(ctx, ImmutableContext)
    assert ctx.canonical_id == "boskuh"
    assert len(ctx.goals) > 0
    assert len(ctx.semantic_memory) > 0
    assert len(ctx.recent_episodes) > 0

def test_injector_cache_hit():
    hck = mock_hck()
    inj = ContextInjector(hck)
    ctx1 = inj.inject("boskuh", "london")
    ctx2 = inj.inject("boskuh", "london")
    assert ctx1 is ctx2  # same object from cache
    assert hck.get_identity.call_count == 1  # only called once

def test_injector_cache_miss_different_session():
    hck = mock_hck()
    inj = ContextInjector(hck)
    ctx1 = inj.inject("boskuh", "london")
    ctx2 = inj.inject("boskuh", "new_york")  # diff session
    assert ctx1 is not ctx2
    assert hck.get_identity.call_count == 2

def test_injector_hck_fail_nonfatal():
    hck = MagicMock()
    hck.get_identity.side_effect = Exception("HCK down")
    hck.get_goals.side_effect = Exception("HCK down")
    hck.get_semantic_memory.return_value = []
    hck.get_recent_episodes.return_value = []
    inj = ContextInjector(hck)
    ctx = inj.inject("x")  # must not raise
    assert ctx.identity == {}
    assert ctx.goals == ()

def test_injector_partial_context():
    # explicit empty goals + episodes, semantic has non-goal only
    hck = mock_hck(
        goals=[],
        episodes=[],
        semantic=[{"category": "fact", "content": "trend bullish"}],
    )
    hck.get_goals.return_value = []  # force goals empty
    inj = ContextInjector(hck)
    ctx = inj.inject("boskuh", "s1")
    assert len(ctx.goals) == 0
    assert len(ctx.recent_episodes) == 0
    assert len(ctx.semantic_memory) > 0

def test_injector_invalidate():
    hck = mock_hck()
    inj = ContextInjector(hck)
    inj.inject("boskuh", "london")
    inj.invalidate()
    inj.inject("boskuh", "london")  # must re-fetch
    assert hck.get_identity.call_count == 2

def test_injector_health_check():
    hck = mock_hck()
    inj = ContextInjector(hck)
    health = inj.health_check("boskuh", "london")
    assert "context_available" in health
    assert health["context_available"] is True
