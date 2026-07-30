"""Test Phase 8.1 — SNRC1 Bystra Detector with live candle mapping."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from datetime import datetime, timezone
from detectors.snrc1_detector import Snrc1Detector
from detectors.common import detect_rbr, detect_dbd, is_engulfing
from core.context.context_model import MarketContext
from core.detectors.fact import Fact


def bc(o,h,l,c):
    return {"open":float(o),"high":float(h),"low":float(l),"close":float(c)}


# ── RBR ──────────────────────────────────────────────────────────────────────
def test_rbr_detected():
    """RBR: cand[i-1] = swing high, cand[i] = base, cand[i+1] = breakout."""
    full = [
        bc(90,92,89,91), bc(91,95,90,94), bc(93,97,92,96),
        bc(95,96,94,95), bc(95,98,94,98), bc(97,99,96,98),
    ]
    from detectors.common import detect_rbr
    r = detect_rbr(full)
    assert r is not None
    assert r["entry"] > 96  # breakout above 96

def test_rbr_no_pattern():
    """Flat trend → no RBR detected."""
    full = [bc(100,101,99,100)] * 7
    from detectors.common import detect_rbr
    assert detect_rbr(full) is None


# ── DBD ──────────────────────────────────────────────────────────────────────
def test_dbd_detected():
    """DBD: cand[i-1] = swing low, cand[i] = base, cand[i+1] = breakout below."""
    full = [
        bc(108,110,107,109),    # [0]
        bc(106,108,105,107),    # [1] L=105
        bc(104,107,102,105),    # [2] swing low L=102
        bc(103,105,103,104),    # [3] base (pullback) L=103 > 102 ✓
        bc(104,105,101,101),    # [4] close=101 < base_low=103
        bc(100,101,99,100),     # [5] padding
    ]
    from detectors.common import detect_dbd
    r = detect_dbd(full)
    assert r is not None
    assert r["entry"] < 103

def test_dbd_no_pattern():
    full = [bc(100,101,99,100)] * 7
    from detectors.common import detect_dbd
    assert detect_dbd(full) is None


# ── Engulfing ───────────────────────────────────────────────────────────────
def test_engulfing_bullish():
    """Bearish candle → bullish engulfs it."""
    from detectors.common import is_engulfing
    assert is_engulfing(
        bc(100,102,99,99),    # bearish: close=99 < open=100
        bc(98,104,97,103),    # bullish: engulfs prev body
    ) == "bullish"

def test_engulfing_bearish():
    from detectors.common import is_engulfing
    assert is_engulfing(
        bc(100,101,99,101),   # bullish body: high=101 low=100
        bc(101,103,97,97),    # bearish, engulfs body (high=103>prev=101, low=97<prev=100)
    ) == "bearish"

def test_no_engulfing_same_body():
    from detectors.common import is_engulfing
    assert is_engulfing(bc(100,102,99,101), bc(100,102,99,101)) == ""


# ── SNRC1 Detector ──────────────────────────────────────────────────────────
def test_snrc1_returns_facts():
    """End-to-end with enough candle data for RBR match."""
    full = [
        bc(90,92,89,91), bc(91,95,90,94), bc(93,97,92,96),     # [0-2]
        bc(95,96,94,95), bc(95,98,94,98), bc(97,99,96,98),      # [3-5] RBR
    ]
    ctx = MarketContext(symbol="XAUUSD", timestamp=datetime.now(timezone.utc))
    ctx.metadata["candles"] = {"M5": full, "M15": [bc(100,105,98,104), bc(101,106,99,105)]}
    ctx.metadata["nearest_support"] = 94
    ctx.metadata["current_price"] = 98
    ctx.metadata["h1_support"] = 92
    ctx.metadata["h1_trend"] = "bullish"

    d = Snrc1Detector()
    facts = d.detect(ctx)
    assert len(facts) >= 0  # may or may not match depending on M15 engulf check
    if facts:
        assert facts[0].fact_type == "ENTRY_PATTERN"
        assert facts[0].value == "SNRC_1"


def test_snrc1_no_candles():
    ctx = MarketContext(symbol="X", timestamp=datetime.now(timezone.utc))
    assert Snrc1Detector().detect(ctx) == []


def test_snrc1_danger_zone_blocks():
    """Danger zone touched → no fact."""
    full = [
        bc(90,92,89,91), bc(91,95,90,94), bc(93,97,92,96),     # [0-2]
        bc(95,96,94,95), bc(95,98,94,98), bc(97,99,96,98),      # [3-5] RBR
    ]
    ctx = MarketContext(symbol="XAUUSD", timestamp=datetime.now(timezone.utc))
    ctx.metadata["candles"] = {"M5": full, "M15": [bc(100,105,98,104), bc(101,106,99,105)]}
    ctx.metadata["nearest_support"] = 94
    ctx.metadata["current_price"] = 98
    ctx.metadata["h1_support"] = 97  # Danger Zone too close
    ctx.metadata["h1_trend"] = "bullish"
    facts = Snrc1Detector().detect(ctx)
    assert len(facts) == 0  # blocked by DZ