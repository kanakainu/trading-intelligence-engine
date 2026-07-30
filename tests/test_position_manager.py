"""Test Phase 4.7 — Position Manager."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timezone
from decimal import Decimal
from position.manager import PositionManager
from position.models import Position, PositionStatus, PositionAuditEntry, PositionHealth
from position.tracker import PositionTracker
from position.synchronizer import PositionSynchronizer
from position.monitor import PositionMonitor
from position.lifecycle import validate_transition
from position.audit import PositionAuditTrail
from position.health import PositionHealthMonitor
from position.registry import PositionRegistry
from position.config import PositionConfig
from position.events import PositionEvent, PositionEventType
from position.exceptions import (
    PositionNotFoundError, PositionSynchronizationError,
    InvalidPositionStateError, PositionLifecycleError,
)

@pytest.fixture
def pm():
    m = PositionManager()
    m.initialize()
    m.start()
    return m

# ── Lifecycle ──────────────────────────────────────────────────────────────
def test_initialize():
    m = PositionManager()
    assert m._status == "CREATED"
    m.initialize()
    assert m._status == "INITIALIZED"

def test_start_stop(pm):
    pm.stop()
    assert pm._status == "STOPPED"

# ── Position Creation ──────────────────────────────────────────────────────
def test_open_position(pm):
    pos = pm.open_position("XAUUSD", "BUY", 0.1, Decimal("1.08000"), Decimal("1.07900"), Decimal("1.08200"))
    assert pos.position_id and pos.status == PositionStatus.OPEN
    assert pos.entry_price == Decimal("1.08000")
    assert pos.symbol == "XAUUSD"

def test_get_position(pm):
    pos = pm.open_position("EURUSD", "SELL", 0.2, Decimal("1.10000"))
    g = pm.get_position(pos.position_id)
    assert g and g.position_id == pos.position_id

def test_get_position_not_found(pm):
    assert pm.get_position("nonexistent") is None

def test_list_positions_active(pm):
    pm.open_position("XAUUSD", "BUY", 0.1, Decimal("1.08"))
    assert len(pm.list_positions(active_only=True)) == 1

# ── Position Update ────────────────────────────────────────────────────────
def test_update_position(pm):
    pos = pm.open_position("XAUUSD", "BUY", 0.1, Decimal("1.08"), Decimal("1.07"))
    updated = pm.update_position(pos.position_id, stop_loss=Decimal("1.069"))
    assert updated.stop_loss == Decimal("1.069")

def test_update_nonexistent(pm):
    with pytest.raises(PositionNotFoundError):
        pm.update_position("nonexistent", volume=0.2)

# ── Position Close ─────────────────────────────────────────────────────────
def test_close_position(pm):
    pos = pm.open_position("XAUUSD", "BUY", 0.1, Decimal("1.08"))
    closed = pm.close_position(pos.position_id, realized_pnl=15.0)
    assert closed.status == PositionStatus.CLOSED
    assert closed.realized_pnl == 15.0
    assert closed.closed_at is not None

def test_close_nonexistent(pm):
    with pytest.raises(PositionNotFoundError):
        pm.close_position("nonexistent")

def test_close_twice(pm):
    pos = pm.open_position("XAUUSD", "BUY", 0.1, Decimal("1.08"))
    pm.close_position(pos.position_id)
    with pytest.raises(InvalidPositionStateError):  # CLOSED → CLOSED invalid
        pm.close_position(pos.position_id)

# ── Lifecycle Transitions ──────────────────────────────────────────────────
def test_lifecycle_open_to_closed():
    assert validate_transition(PositionStatus.OPEN, PositionStatus.CLOSED)

def test_lifecycle_invalid():
    with pytest.raises(InvalidPositionStateError):
        validate_transition(PositionStatus.CLOSED, PositionStatus.OPEN)

def test_lifecycle_created_to_submitted():
    assert validate_transition(PositionStatus.CREATED, PositionStatus.SUBMITTED)

def test_lifecycle_open_to_modified():
    assert validate_transition(PositionStatus.OPEN, PositionStatus.MODIFIED)

def test_lifecycle_closed_to_anything_raises():
    with pytest.raises(InvalidPositionStateError):
        validate_transition(PositionStatus.CLOSED, PositionStatus.OPEN)

# ── Synchronization ────────────────────────────────────────────────────────
def test_synchronize_new_position(pm):
    changes = pm.synchronize([
        {"position_id": "brk_001", "symbol": "XAUUSD", "side": "BUY",
         "volume": 0.1, "entry_price": Decimal("1.08"), "current_price": Decimal("1.081")}
    ])
    assert changes == 1
    assert pm.get_position("brk_001") is not None

def test_synchronize_update(pm):
    pm.synchronize([
        {"position_id": "brk_001", "symbol": "XAUUSD", "side": "BUY",
         "volume": 0.1, "entry_price": Decimal("1.08"), "current_price": Decimal("1.08")}
    ])
    changes = pm.synchronize([
        {"position_id": "brk_001", "symbol": "XAUUSD", "side": "BUY",
         "volume": 0.1, "entry_price": Decimal("1.08"), "current_price": Decimal("1.082"), "unrealized_pnl": 2.0}
    ])
    assert changes == 1
    assert pm.get_position("brk_001").unrealized_pnl == 2.0

def test_synchronize_detect_close(pm):
    pm.synchronize([
        {"position_id": "brk_001", "symbol": "XAUUSD", "side": "BUY",
         "volume": 0.1, "entry_price": Decimal("1.08"), "current_price": Decimal("1.08")}
    ])
    assert len(pm.list_positions(active_only=True)) == 1
    # Second sync without brk_001 -> should close it
    changes = pm.synchronize([])
    assert changes == 1
    assert len(pm.list_positions(active_only=True)) == 0  # no longer active

# ── Monitoring ─────────────────────────────────────────────────────────────
def test_monitor_on_opened(pm):
    events = []
    pm.set_publish_fn(lambda e: events.append(e.event_type))
    pm.open_position("XAUUSD", "BUY", 0.1, Decimal("1.08"))
    assert PositionEventType.POSITION_OPENED in events

def test_monitor_on_closed(pm):
    events = []
    pm.set_publish_fn(lambda e: events.append(e.event_type))
    pos = pm.open_position("XAUUSD", "BUY", 0.1, Decimal("1.08"))
    pm.close_position(pos.position_id)
    assert PositionEventType.POSITION_CLOSED in events

# ── Audit Trail ────────────────────────────────────────────────────────────
def test_audit_on_open(pm):
    pos = pm.open_position("XAUUSD", "BUY", 0.1, Decimal("1.08"))
    entries = pm.audit.get_entries(pos.position_id)
    assert len(entries) == 1
    assert entries[0].current_status == PositionStatus.OPEN.value

def test_audit_on_close(pm):
    pos = pm.open_position("XAUUSD", "BUY", 0.1, Decimal("1.08"))
    pm.close_position(pos.position_id)
    entries = pm.audit.get_entries(pos.position_id)
    assert len(entries) == 2

# ── Health ─────────────────────────────────────────────────────────────────
def test_health_check(pm):
    h = pm.health_check()
    assert isinstance(h, PositionHealth)
    assert h.active_positions >= 0

def test_health_updates(pm):
    pm.open_position("XAUUSD", "BUY", 0.1, Decimal("1.08"))
    assert pm.health_check().active_positions == 1

# ── Registry ───────────────────────────────────────────────────────────────
def test_registry_monitor(pm):
    pm.registry.register_monitor("test", lambda: None)
    assert "test" in pm.registry.list_monitors()

def test_registry_lifecycle_handler(pm):
    pm.registry.register_lifecycle_handler("log", lambda: None)
    assert "log" in pm.registry.list_lifecycle_handlers()

def test_registry_sync_handler(pm):
    pm.registry.register_sync_handler("validate", lambda: None)
    assert "validate" in pm.registry.list_sync_handlers()

# ── Tracker ────────────────────────────────────────────────────────────────
def test_tracker_list_by_symbol(pm):
    pm.open_position("EURUSD", "BUY", 0.1, Decimal("1.10"))
    pm.open_position("XAUUSD", "BUY", 0.1, Decimal("1.08"))
    assert len(pm.tracker.list_by_symbol("XAUUSD")) == 1

def test_tracker_count(pm):
    assert pm.tracker.count_active() == 0
    pm.open_position("XAUUSD", "BUY", 0.1, Decimal("1.08"))
    assert pm.tracker.count_active() == 1

# ── Exceptions ─────────────────────────────────────────────────────────────
def test_exceptions():
    with pytest.raises(PositionNotFoundError): raise PositionNotFoundError("x")
    with pytest.raises(InvalidPositionStateError): raise InvalidPositionStateError("x")
    with pytest.raises(PositionSynchronizationError): raise PositionSynchronizationError("x")
    with pytest.raises(PositionLifecycleError): raise PositionLifecycleError("x")

# ── Phase 3 frozen ─────────────────────────────────────────────────────────
def test_phase3_frozen():
    from core.decision.decision_pipeline import DecisionPipeline
    assert DecisionPipeline
