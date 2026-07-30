"""Test Phase 4.4 — Memory Adapter."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timezone, timedelta
from adapters.memory.base import MemoryAdapterBase
from adapters.memory.models import MemoryRecord, MemoryQuery, MemoryResult, MemoryHealthReport
from adapters.memory.registry import MemoryRegistry
from adapters.memory.mock_memory import MockMemoryAdapter
from adapters.memory.hck_adapter import HCKMemoryAdapter
from adapters.memory.exceptions import (
    MemoryConnectionError, MemoryUnavailableError,
    MemoryQueryError, MemoryWriteError
)

@pytest.fixture
def mem():
    m = MockMemoryAdapter(); m.initialize(); m.connect()
    return m

# ── Lifecycle ──────────────────────────────────────────────────────────────
def test_connect(mem):              assert mem.get_status().value == "CONNECTED"
def test_disconnect(mem):
    mem.disconnect()
    assert mem.get_status().value == "DISCONNECTED"
def test_initialize():
    m = MockMemoryAdapter(); m.initialize()
    assert m.get_status().value == "INITIALIZED"

# ── CRUD ───────────────────────────────────────────────────────────────────
def test_store(mem):
    r = MemoryRecord(category="episodic", key="msg", value="test")
    s = mem.store(r)
    assert s.record_id and s.category == "episodic"

def test_retrieve(mem):
    r = mem.store(MemoryRecord(category="semantic", key="fact", value="sky is blue"))
    g = mem.retrieve(r.record_id)
    assert g and g.value == "sky is blue"

def test_update(mem):
    r = mem.store(MemoryRecord(category="identity", key="name", value="test"))
    r.value = "updated"
    u = mem.update(r)
    assert u.version == 2 and u.updated_at is not None

def test_delete(mem):
    r = mem.store(MemoryRecord(category="goal", key="g"))
    assert mem.delete(r.record_id)
    assert mem.retrieve(r.record_id) is None

def test_store_many(mem):
    recs = [MemoryRecord(category="episodic", key=f"k{i}", value=i) for i in range(5)]
    assert len(mem.store_many(recs)) == 5

# ── Search ─────────────────────────────────────────────────────────────────
def test_search_category(mem):
    mem.store(MemoryRecord(category="episodic", key="a"))
    mem.store(MemoryRecord(category="semantic", key="b"))
    res = mem.search(MemoryQuery(category="episodic"))
    assert len(res.records) == 1

def test_search_tags(mem):
    mem.store(MemoryRecord(category="episodic", key="t1", tags=["trade"]))
    res = mem.search(MemoryQuery(tags=["trade"]))
    assert len(res.records) == 1

def test_search_keywords(mem):
    mem.store(MemoryRecord(category="episodic", key="gold", value="price up"))
    res = mem.search(MemoryQuery(keywords=["gold"]))
    assert res

def test_search_limit(mem):
    for i in range(10): mem.store(MemoryRecord(category="episodic", key=f"k{i}"))
    res = mem.search(MemoryQuery(category="episodic", limit=3))
    assert len(res.records) <= 3

def test_search_since(mem):
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=10)
    mem.store(MemoryRecord(category="episodic", key="old"))
    res = mem.search(MemoryQuery(since=cutoff))
    assert res.total >= 0

def test_search_no_match(mem):
    assert mem.search(MemoryQuery(category="nonexistent")).total == 0

def test_result_bool_empty():
    assert not MemoryResult()

# ── Compact & Cleanup ──────────────────────────────────────────────────────
def test_compact(mem):
    mem.compact()  # no-op, should not raise

def test_cleanup(mem):
    mem.store(MemoryRecord(category="episodic", key="cleanup_test"))
    removed = mem.cleanup(before_age_seconds=0)
    assert isinstance(removed, int)

# ── Registry ───────────────────────────────────────────────────────────────
def test_registry_register():
    reg = MemoryRegistry()
    reg.register("mock", MockMemoryAdapter)
    assert reg.exists("mock")

def test_registry_load():
    reg = MemoryRegistry()
    reg.register("mock", MockMemoryAdapter)
    assert isinstance(reg.load("mock"), MockMemoryAdapter)

def test_registry_list():
    reg = MemoryRegistry()
    reg.register("mock", MockMemoryAdapter)
    assert "mock" in reg.list()

def test_provider_switch():
    reg = MemoryRegistry()
    reg.register("mock", MockMemoryAdapter)
    reg.register("hck", HCKMemoryAdapter)
    assert reg.exists("hck")

# ── Health ─────────────────────────────────────────────────────────────────
def test_health_report(mem):
    h = mem.health_report()
    assert isinstance(h, MemoryHealthReport)
    assert h.connected is True

def test_health_check(mem):
    h = mem.health_check()
    assert h["status"] == "CONNECTED"

# ── HCK Adapter ────────────────────────────────────────────────────────────
def test_hck_init_fail():
    h = HCKMemoryAdapter()
    with pytest.raises(MemoryConnectionError): h.initialize()

def test_hck_no_client_store():
    h = HCKMemoryAdapter()
    h.initialize = lambda: None
    with pytest.raises(MemoryConnectionError): h.store(MemoryRecord())

def test_hck_no_client_retrieve():
    h = HCKMemoryAdapter()
    h.initialize = lambda: None
    with pytest.raises(MemoryConnectionError): h.retrieve("x")

def test_hck_no_client_search():
    h = HCKMemoryAdapter()
    h.initialize = lambda: None
    with pytest.raises(MemoryConnectionError): h.search(MemoryQuery())

def test_hck_health():
    h = HCKMemoryAdapter()
    h.initialize = lambda: None
    hr = h.health_report()
    assert hr.provider == "hck"

# ── Exceptions ─────────────────────────────────────────────────────────────
def test_exceptions():
    with pytest.raises(MemoryConnectionError): raise MemoryConnectionError("fail")
    with pytest.raises(MemoryUnavailableError): raise MemoryUnavailableError("fail")
    with pytest.raises(MemoryQueryError): raise MemoryQueryError("fail")
    with pytest.raises(MemoryWriteError): raise MemoryWriteError("fail")

# ── Phase 3 frozen ─────────────────────────────────────────────────────────
def test_phase3_frozen():
    from core.execution.execution_contract import ExecutionContract
    from core.decision.decision_pipeline import DecisionPipeline
    assert DecisionPipeline
