"""Test Sprint 6.1 — HCK Bridge."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import MagicMock, patch
from adapters.hck_bridge import HCKBridge
from adapters.memory_provider import MemoryProvider
from adapters.context_provider import ContextProvider
from adapters.episode_writer import EpisodeWriter
from adapters.reflection_writer import ReflectionWriter
from adapters.semantic_reader import SemanticReader
from adapters.event_dispatcher import EventDispatcher


def make_mock_hck():
    m = MagicMock()
    m.get_episodic_memory.return_value = [{"role": "user", "content": "buy signal"}]
    m.get_semantic_memory.return_value = [{"category": "fact", "content": "bullish"}]
    m.get_contact.return_value = {"name": "Boskuh", "lid": "test123"}
    m.store_turn.return_value = None
    m.store_semantic.return_value = None
    return m


@pytest.fixture
def bridge():
    b = HCKBridge(workspace="boskuh", agent_id="riri")
    b._client = make_mock_hck()
    b._connected = True
    return b


# ── Initialization ─────────────────────────────────────────────────────────
def test_bridge_initialize_no_hck():
    b = HCKBridge()
    # HCK might not be available in test env — should not crash
    b.initialize()
    # either connected or gracefully degraded
    assert isinstance(b.health_check(), dict)

def test_bridge_health_when_connected(bridge):
    h = bridge.health_check()
    assert h["connected"] is True
    assert h["status"] == "HEALTHY"

def test_bridge_health_when_disconnected():
    b = HCKBridge()
    h = b.health_check()
    assert h["connected"] is False
    assert h["status"] == "DISCONNECTED"


# ── Context ────────────────────────────────────────────────────────────────
def test_get_context_returns_dict(bridge):
    ctx = bridge.get_context("boskuh_id")
    assert "episodic" in ctx
    assert "semantic" in ctx

def test_get_context_no_client():
    b = HCKBridge()
    ctx = b.get_context("any_id")
    assert ctx == {}


# ── Episodic ───────────────────────────────────────────────────────────────
def test_get_recent_episodes(bridge):
    eps = bridge.get_recent_episodes("boskuh_id", limit=3)
    assert isinstance(eps, list)
    bridge._client.get_episodic_memory.assert_called_with("boskuh_id", limit=3, agent_id="riri")

def test_get_episodes_no_client():
    b = HCKBridge()
    assert b.get_recent_episodes("x") == []


# ── Semantic ───────────────────────────────────────────────────────────────
def test_get_semantic_memory(bridge):
    sem = bridge.get_semantic_memory("boskuh_id")
    assert isinstance(sem, list)

def test_get_identity(bridge):
    ident = bridge.get_identity("test123")
    assert "name" in ident

def test_get_goals_filters_by_category(bridge):
    bridge._client.get_semantic_memory.return_value = [
        {"category": "goal", "content": "earn $30"},
        {"category": "fact", "content": "bullish"},
    ]
    goals = bridge.get_goals("boskuh_id")
    assert all(g["category"] == "goal" for g in goals)
    assert len(goals) == 1


# ── Writers ────────────────────────────────────────────────────────────────
def test_write_episode(bridge):
    ok = bridge.write_episode("boskuh_id", "buy XAUUSD", "order placed")
    assert ok is True
    bridge._client.store_turn.assert_called_once()

def test_write_reflection(bridge):
    ok = bridge.write_reflection("boskuh_id", "trend is bullish", "reflection")
    assert ok is True
    bridge._client.store_semantic.assert_called_once()

def test_write_episode_no_client():
    b = HCKBridge()
    assert b.write_episode("x", "u", "r") is False

def test_write_reflection_no_client():
    b = HCKBridge()
    assert b.write_reflection("x", "content") is False


# ── Event dispatcher ───────────────────────────────────────────────────────
def test_publish_event(bridge):
    ok = bridge.publish_event("DECISION_RECEIVED", {"canonical_id": "boskuh_id", "action": "BUY"})
    assert ok is True

def test_publish_event_no_client():
    b = HCKBridge()
    assert b.publish_event("X", {}) is False


# ── Sub-modules ────────────────────────────────────────────────────────────
def test_memory_provider(bridge):
    mp = MemoryProvider(bridge)
    assert isinstance(mp.get_episodic("id"), list)
    assert isinstance(mp.get_semantic("id"), list)

def test_context_provider(bridge):
    cp = ContextProvider(bridge)
    ctx = cp.build_context("boskuh_id")
    assert "episodic" in ctx and "semantic" in ctx and "identity" in ctx

def test_episode_writer(bridge):
    ew = EpisodeWriter(bridge)
    assert ew.write("id", "msg", "reply") is True

def test_reflection_writer(bridge):
    rw = ReflectionWriter(bridge)
    assert rw.write("id", "reflection content") is True

def test_semantic_reader(bridge):
    sr = SemanticReader(bridge)
    assert isinstance(sr.read("id"), list)

def test_event_dispatcher(bridge):
    ed = EventDispatcher(bridge)
    assert ed.dispatch("TEST_EVENT", {"canonical_id": "id"}) is True


# ── Boundary: TIE modules must not import HCK directly ───────────────────
def test_no_direct_hck_import_in_runtime():
    import ast, pathlib
    banned = {"hck_service", "hck_memory_manager", "hck_cre", "MemoryManager"}
    for f in pathlib.Path("runtime").glob("*.py"):
        src = f.read_text()
        for b in banned:
            assert b not in src, f"runtime/{f.name} imports banned HCK module: {b}"

def test_hck_bridge_is_only_entry_point():
    """All HCK access in adapters must go through hck_bridge.py."""
    import pathlib
    for f in pathlib.Path("adapters").glob("*.py"):
        if f.name == "hck_bridge.py" or f.name == "hck_adapter.py":
            continue
        src = f.read_text()
        assert "hck_service" not in src, f"{f.name} imports hck_service directly"
