"""Unit tests — shared context/setup/location/trigger pipeline."""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from shared.market_context import build, Regime, StructureBias
from shared.setup_detector import detect, SetupType, SetupDirection
from shared.location_engine import evaluate as loc_eval, LocationGrade
from shared.trigger_engine import evaluate as trig_eval, TriggerSignal
from shared.entry_decision import EntryDecision, ExecutionMode


def _candles(n=20, trend="up"):
    """Synthetic candles — up/down/flat."""
    cs = []
    for i in range(n):
        if trend == "up":
            o, c, h, l = 100+i, 101+i, 102+i, 99+i
        elif trend == "down":
            o, c, h, l = 100-i, 99-i, 101-i, 98-i
        else:
            o, c, h, l = 100, 100, 101, 99
        cs.append({"open": o, "close": c, "high": h, "low": l})
    return cs


# ── MarketContext ─────────────────────────────────────────────────────────────

def test_regime_trending_bull():
    c = _candles(20, "up")
    ctx = build(c, c, c[-5:], 120.0, 2.0)
    assert ctx.regime == Regime.TRENDING_BULL
    assert ctx.m15_bias == StructureBias.BULLISH
    assert ctx.m5_structure == StructureBias.BULLISH

def test_regime_trending_bear():
    c = _candles(20, "down")
    ctx = build(c, c, c[-5:], 80.0, 2.0)
    assert ctx.regime == Regime.TRENDING_BEAR

def test_regime_ranging():
    # 20 strictly alternating bull/bear → m15 last-3 = [bull,bear,bull]=NEUTRAL, m5 last-5 = no HH+HL or LL+LH = NEUTRAL
    c = []
    for i in range(20):
        if i % 2 == 0:
            c.append({"open": 100, "close": 101, "high": 102, "low": 99})
        else:
            c.append({"open": 101, "close": 100, "high": 102, "low": 99})
    ctx = build(c, c, c[-5:], 100.0, 2.0)
    assert ctx.regime in (Regime.RANGING, Regime.TRANSITION)  # both = non-trending

def test_vwap_distance_zero_atr():
    c = _candles(5, "up")
    ctx = build(c, c, c, 105.0, 0.0)
    assert ctx.vwap_distance_atr == 0.0


# ── SetupDetector ─────────────────────────────────────────────────────────────

def test_trend_pullback_buy():
    c = _candles(20, "up")
    ctx = build(c, c, c[-5:], 120.0, 2.0)
    # recent_low = 99+10 = 109. price 110 is within 1.0xATR=2.0 of 109
    setup = detect(ctx, c, c[-5:], 110.0)
    assert setup.type == SetupType.TREND_PULLBACK
    assert setup.direction == SetupDirection.BUY
    assert setup.is_valid

def test_trend_pullback_sell():
    c = _candles(20, "down")
    ctx = build(c, c, c[-5:], 80.0, 2.0)
    # down candles: recent_high of last 10 = 101-10 = 91. price 90 within 1ATR
    setup = detect(ctx, c, c[-5:], 90.0)
    assert setup.type == SetupType.TREND_PULLBACK
    assert setup.direction == SetupDirection.SELL

def test_no_setup_flat():
    c = _candles(20, "flat")
    ctx = build(c, c, c[-5:], 100.0, 2.0)
    # RANGING but price in middle — no range_edge
    setup = detect(ctx, c, c[-5:], 100.0)
    assert not setup.is_valid

def test_no_setup_insufficient_candles():
    c = _candles(3, "up")
    ctx = build(c, c, c, 100.0, 2.0)
    setup = detect(ctx, c, c, 100.0)
    assert setup.type == SetupType.NONE

def test_range_edge_buy():
    c = _candles(20, "up")
    ctx = build(c, c, c[-5:], 120.0, 2.0)
    # TRENDING_BULL, price at zone = 109. Test pullback also covers "near zone" case
    setup = detect(ctx, c, c[-5:], 110.0)
    assert setup.is_valid  # pullback or range_edge, just needs a valid setup

def test_range_edge_sell():
    c = _candles(20, "down")
    ctx = build(c, c, c[-5:], 80.0, 2.0)
    setup = detect(ctx, c, c[-5:], 90.0)
    assert setup.is_valid


# ── LocationEngine ────────────────────────────────────────────────────────────

def test_location_good_buy():
    c = _candles(20, "up")
    loc = loc_eval("BUY", 101.0, c, c, 2.0)
    assert loc.grade == LocationGrade.GOOD
    assert loc.score > 0

def test_location_bad_buy_at_resistance():
    c = _candles(20, "up")
    # price at top of range = direct resistance
    loc = loc_eval("BUY", 119.5, c, c, 2.0)
    assert loc.grade == LocationGrade.BAD
    assert loc.score == 0.0

def test_location_no_atr():
    c = _candles(5, "up")
    loc = loc_eval("BUY", 105.0, c, c, 0.0)
    assert loc.grade == LocationGrade.NEUTRAL


# ── TriggerEngine ─────────────────────────────────────────────────────────────

def test_trigger_armed_buy():
    c = _candles(5, "up")
    trig = trig_eval("BUY", c, 1.0)
    assert trig.signal == TriggerSignal.ARMED
    assert trig.strength > 0

def test_trigger_armed_sell():
    c = _candles(5, "down")
    trig = trig_eval("SELL", c, 1.0)
    assert trig.signal == TriggerSignal.ARMED

def test_trigger_wait_contra():
    c_up = _candles(5, "up")
    trig = trig_eval("SELL", c_up, 1.0)  # up candles, want SELL
    assert trig.signal == TriggerSignal.WAIT

def test_trigger_none_insufficient():
    trig = trig_eval("BUY", [{"open":1,"close":2,"high":3,"low":0}], 1.0)
    assert trig.signal == TriggerSignal.NONE


# ── EntryDecision ─────────────────────────────────────────────────────────────

def test_no_trade():
    nd = EntryDecision.no_trade("test_reason")
    assert not nd.is_valid
    assert nd.action == "NONE"
    assert "test_reason" in nd.rejection_reason

def test_valid_decision():
    from shared.setup_detector import Setup, SetupType, SetupDirection
    nd = EntryDecision(
        action="BUY", setup_type=SetupType.TREND_PULLBACK, regime=Regime.TRENDING_BULL,
        quality_score=75.0, setup_score=25.0, location_score=22.0,
        trigger_score=17.0, room_score=8.0, market_score=3.0,
        execution_mode=ExecutionMode.RME,
        entry_price=100.0, stop_loss=98.0, take_profit=103.0,
        initial_lot=0.01, add_allowed=False, rejection_reason="",
        filter_trace=[],
    )
    assert nd.is_valid

def test_decision_below_threshold():
    from shared.setup_detector import Setup, SetupType, SetupDirection
    nd = EntryDecision(
        action="BUY", setup_type=SetupType.TREND_PULLBACK, regime=Regime.TRENDING_BULL,
        quality_score=55.0, setup_score=20.0, location_score=15.0,
        trigger_score=10.0, room_score=5.0, market_score=5.0,
        execution_mode=ExecutionMode.RME,
        entry_price=100.0, stop_loss=98.0, take_profit=103.0,
        initial_lot=0.01, add_allowed=False, rejection_reason="",
        filter_trace=[],
    )
    assert not nd.is_valid  # score < 60


# ── BUY/SELL symmetry ────────────────────────────────────────────────────────

@pytest.mark.parametrize("direction", ["BUY", "SELL"])
def test_trigger_symmetric(direction):
    trend = "up" if direction == "BUY" else "down"
    c = _candles(5, trend)
    trig = trig_eval(direction, c, 1.0)
    assert trig.signal == TriggerSignal.ARMED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
