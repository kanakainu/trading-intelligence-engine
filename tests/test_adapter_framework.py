"""Test Phase 4.1 — Adapter Framework."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from adapters.base import BaseAdapter
from adapters.registry import AdapterRegistry
from adapters.lifecycle import AdapterState
from adapters.exceptions import (
    AdapterError, ConnectionError, AuthenticationError,
    UnsupportedCapabilityError, AdapterTimeoutError,
)
from adapters.health import collect


class DummyAdapter(BaseAdapter):
    @property
    def name(self): return "dummy"
    def initialize(self): self._set_state(AdapterState.INITIALIZED)
    def connect(self):    self._set_state(AdapterState.CONNECTED)
    def disconnect(self): self._set_state(AdapterState.DISCONNECTED)
    def health_check(self): return self._health(latency=1.0)

@pytest.fixture
def reg():
    r = AdapterRegistry()
    r.register("dummy", DummyAdapter)
    return r

# ── lifecycle ──────────────────────────────────────────────────────────────
def test_initial_state():   assert DummyAdapter().get_status() == AdapterState.CREATED
def test_initialize():
    a = DummyAdapter(); a.initialize()
    assert a.get_status() == AdapterState.INITIALIZED
def test_connect():
    a = DummyAdapter(); a.initialize(); a.connect()
    assert a.get_status() == AdapterState.CONNECTED
def test_disconnect():
    a = DummyAdapter(); a.initialize(); a.connect(); a.disconnect()
    assert a.get_status() == AdapterState.DISCONNECTED

# ── registry ───────────────────────────────────────────────────────────────
def test_register(reg):     assert reg.available("dummy")
def test_discover(reg):     assert "dummy" in reg.discover()
def test_load(reg):         assert isinstance(reg.load("dummy"), DummyAdapter)
def test_load_missing(reg): assert reg.load("nope") is None

# ── health ─────────────────────────────────────────────────────────────────
def test_health_fields():
    a = DummyAdapter(); a.initialize()
    h = a.health_check()
    for f in ["name","status","latency","last_check","error"]:
        assert f in h
def test_health_collect(reg):
    results = collect(reg)
    assert len(results) == 1 and results[0]["name"] == "dummy"

# ── exceptions ─────────────────────────────────────────────────────────────
def test_connection_error():
    with pytest.raises(ConnectionError): raise ConnectionError("fail")
def test_auth_error():
    with pytest.raises(AuthenticationError): raise AuthenticationError("fail")
def test_capability_error():
    with pytest.raises(UnsupportedCapabilityError): raise UnsupportedCapabilityError("fail")
def test_timeout_error():
    with pytest.raises(AdapterTimeoutError): raise AdapterTimeoutError("fail")
def test_base_abstract():
    with pytest.raises(TypeError): BaseAdapter()

# ── phase3 frozen ──────────────────────────────────────────────────────────
def test_phase3_unmodified():
    from core.execution.execution_contract import ExecutionContract
    from core.decision.decision_pipeline import DecisionPipeline
    assert DecisionPipeline
