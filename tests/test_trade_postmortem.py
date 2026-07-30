"""Test Sprint 6.5 — Trade Postmortem Writer."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import MagicMock
from runtime.trade_postmortem import TradePostmortemWriter, TradeOutcome


def make_outcome(**kwargs):
    defaults = dict(
        position_id="p001", symbol="XAUUSD", direction="BUY",
        setup="SNRC_1", entry=2000.0, exit_price=2020.0,
        sl=1990.0, tp=2020.0, realized_pnl=20.0, confidence=0.8
    )
    defaults.update(kwargs)
    return TradeOutcome(**defaults)


def mock_hck():
    h = MagicMock()
    h.write_reflection.return_value = True
    h.publish_event.return_value = True
    return h


# ── TradeOutcome ───────────────────────────────────────────────────────────
def test_outcome_win():    assert make_outcome(realized_pnl=20.0).outcome == "WIN"
def test_outcome_loss():   assert make_outcome(realized_pnl=-10.0).outcome == "LOSS"
def test_outcome_be():     assert make_outcome(realized_pnl=0.0).outcome == "BREAKEVEN"

def test_hit_tp_buy():
    o = make_outcome(direction="BUY", entry=2000.0, tp=2020.0, exit_price=2020.0)
    assert o.hit_tp is True

def test_hit_sl_buy():
    o = make_outcome(direction="BUY", entry=2000.0, sl=1990.0, exit_price=1990.0)
    assert o.hit_sl is True

def test_hit_tp_sell():
    o = make_outcome(direction="SELL", entry=2000.0, tp=1980.0, exit_price=1980.0)
    assert o.hit_tp is True

def test_hit_sl_sell():
    o = make_outcome(direction="SELL", entry=2000.0, sl=2010.0, exit_price=2010.0)
    assert o.hit_sl is True

def test_manual_close():
    o = make_outcome(direction="BUY", entry=2000.0, sl=1990.0, tp=2020.0, exit_price=2010.0)
    assert not o.hit_tp and not o.hit_sl


# ── TradePostmortemWriter ─────────────────────────────────────────────────
def test_write_win():
    hck = mock_hck()
    w = TradePostmortemWriter(hck)
    ok = w.write("boskuh", make_outcome(realized_pnl=20.0))
    assert ok is True
    hck.write_reflection.assert_called_once()
    call_args = hck.write_reflection.call_args
    assert "WIN" in call_args[0][1]
    assert "SNRC_1" in call_args[0][1]

def test_write_loss():
    hck = mock_hck()
    w = TradePostmortemWriter(hck)
    ok = w.write("boskuh", make_outcome(realized_pnl=-10.0, exit_price=1990.0))
    assert ok is True
    content = hck.write_reflection.call_args[0][1]
    assert "LOSS" in content

def test_write_publishes_event():
    hck = mock_hck()
    w = TradePostmortemWriter(hck)
    w.write("boskuh", make_outcome())
    hck.publish_event.assert_called_once_with("TRADE_POSTMORTEM", pytest.approx({
        "canonical_id": "boskuh", "position_id": "p001",
        "symbol": "XAUUSD", "outcome": "WIN", "pnl": 20.0, "setup": "SNRC_1"
    }, abs=1))

def test_write_hck_fail_nonfatal():
    hck = MagicMock()
    hck.write_reflection.side_effect = Exception("HCK down")
    w = TradePostmortemWriter(hck)
    ok = w.write("x", make_outcome())
    assert ok is False  # doesn't crash

def test_write_no_hck():
    w = TradePostmortemWriter(None)
    assert w.write("x", make_outcome()) is False

def test_postmortem_content_has_entry_exit():
    hck = mock_hck()
    w = TradePostmortemWriter(hck)
    w.write("boskuh", make_outcome(entry=2000.0, exit_price=2020.0))
    content = hck.write_reflection.call_args[0][1]
    assert "2000" in content
    assert "2020" in content

def test_postmortem_exit_reason_tp():
    hck = mock_hck()
    w = TradePostmortemWriter(hck)
    o = make_outcome(direction="BUY", entry=2000.0, sl=1990.0, tp=2020.0, exit_price=2019.9)
    w.write("boskuh", o)
    content = hck.write_reflection.call_args[0][1]
    assert "TP_HIT" in content

def test_category_is_trade_postmortem():
    hck = mock_hck()
    w = TradePostmortemWriter(hck)
    w.write("boskuh", make_outcome())
    # category passed as keyword arg
    kwargs = hck.write_reflection.call_args[1]
    assert kwargs.get("category") == "trade_postmortem"
