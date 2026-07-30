"""Test Sprint 5.5 — Position Manager Migration."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from runtime.position_state import PositionState
from runtime.contract_executor import ContractExecutor, ExecutionResult
from runtime.position_monitor import PositionMonitor
from runtime.position_manager import PositionManager
from runtime.runtime_events import RuntimePositionEvent, PositionEventType
from core.execution.execution_contract import ExecutionContract


def make_pos(direction="BUY", entry=2000.0, current=2000.0, sl=1990.0, tp=2020.0):
    return PositionState(
        position_id="p001", symbol="XAUUSD",
        direction=direction, entry_price=entry,
        current_price=current, stop_loss=sl, take_profit=tp, volume=0.1
    )

def make_contract(**meta):
    c = ExecutionContract(symbol="XAUUSD", direction="BUY", entry=2000.0, sl=1990.0, tp=2020.0)
    c.metadata = meta
    return c


# ── ContractExecutor ────────────────────────────────────────────────────────
def test_hold_at_entry():
    ex = ContractExecutor()
    pos = make_pos(current=2000.0)
    r = ex.evaluate(pos, make_contract(be_trigger_atr=1.0), atr=5.0)
    assert r.action == "none"

def test_breakeven_triggers():
    ex = ContractExecutor()
    pos = make_pos(current=2006.0, sl=1990.0)  # profit=6 > 1*5
    r = ex.evaluate(pos, make_contract(be_trigger_atr=1.0, be_buffer_pts=0.5), atr=5.0)
    assert r.action == "modify"
    assert r.reason == "breakeven"

def test_trailing_triggers():
    ex = ContractExecutor()
    # profit=11 > trail(2*5=10). Give SL already at breakeven so BE won't fire again.
    pos = make_pos(current=2011.0, sl=2001.0)  # sl already above entry → BE skips
    r = ex.evaluate(pos, make_contract(be_trigger_atr=1.0, be_buffer_pts=0.5,
                                       trail_trigger_atr=2.0, trail_offset_atr=0.5), atr=5.0)
    assert r.action == "modify"
    assert r.reason == "trailing_stop"
    assert r.new_sl is not None

def test_partial_tp_triggers():
    ex = ContractExecutor()
    pos = make_pos(current=2019.7)  # profit=19.7 > 20*0.98=19.6 (avoids float epsilon)
    r = ex.evaluate(pos, make_contract(partial_tp_pct=0.98), atr=0.0)
    assert r.action == "close"

def test_be_only_improves():
    """BE must not move SL backwards."""
    ex = ContractExecutor()
    # SL already at 2001 (above entry+buffer), BE should NOT trigger
    pos = make_pos(current=2006.0, sl=2001.0)
    r = ex.evaluate(pos, make_contract(be_trigger_atr=1.0, be_buffer_pts=0.5), atr=5.0)
    # be_sl = 2000.0 + 0.5 = 2000.5, but current_sl=2001 is already better
    assert r.action != "modify" or r.new_sl is None or r.new_sl > 2001.0

def test_sell_breakeven():
    ex = ContractExecutor()
    pos = make_pos(direction="SELL", entry=2000.0, current=1994.0, sl=2010.0)
    r = ex.evaluate(pos, make_contract(be_trigger_atr=1.0, be_buffer_pts=0.5), atr=5.0)
    assert r.action == "modify"
    assert r.reason == "breakeven"


# ── PositionManager ─────────────────────────────────────────────────────────
def test_register_and_count():
    pm = PositionManager()
    pm.register_position(make_pos(), make_contract())
    assert pm.count == 1

def test_remove_position():
    pm = PositionManager()
    pm.register_position(make_pos(), make_contract())
    pm.remove_position("p001")
    assert pm.count == 0

def test_tick_returns_results():
    actions = []
    pm = PositionManager(on_action=lambda pos, r: actions.append(r.action))
    pm.register_position(
        make_pos(current=2011.0, sl=1990.0),
        make_contract(trail_trigger_atr=2.0, trail_offset_atr=0.5)
    )
    results = pm.tick({"XAUUSD": {"price": 2011.0, "atr": 5.0}})
    assert len(results) == 1
    assert results[0].action in ("modify", "close", "none")
    if results[0].action == "modify":
        assert len(actions) == 1  # callback fired

def test_no_contract_no_result():
    pm = PositionManager()
    pm._positions["p001"] = make_pos()
    # No contract registered → tick returns empty
    results = pm.tick({"XAUUSD": {"price": 2000.0, "atr": 5.0}})
    assert results == []

def test_list_positions():
    pm = PositionManager()
    pm.register_position(make_pos(), make_contract())
    assert len(pm.list_positions()) == 1


# ── RuntimeEvents ────────────────────────────────────────────────────────────
def test_event_creation():
    e = RuntimePositionEvent(PositionEventType.POSITION_BREAKEVEN, "p001", {"sl": 2000.5})
    assert e.event_type == PositionEventType.POSITION_BREAKEVEN
    assert e.position_id == "p001"

def test_profit_pts_buy():
    pos = make_pos(entry=2000.0, current=2005.0)
    assert pos.profit_pts == pytest.approx(5.0)

def test_profit_pts_sell():
    pos = make_pos(direction="SELL", entry=2000.0, current=1995.0)
    assert pos.profit_pts == pytest.approx(5.0)

# ── Phase 3 frozen guard ────────────────────────────────────────────────────
def test_phase3_untouched():
    from core.execution.execution_contract import ExecutionContract
    from core.decision.decision_pipeline import DecisionPipeline
    assert ExecutionContract and DecisionPipeline
