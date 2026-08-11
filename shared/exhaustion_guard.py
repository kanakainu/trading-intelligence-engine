"""Exhaustion Guard — Multi-TF conflict filter (Nexus A5/A6 debate style).

Blocks entries that fight the bigger picture:
  - BUY when M5 price is overextended above VWAP (exhausted push up)
  - SELL when M5 price is overextended below VWAP (exhausted dump down)
  - BUY/SELL when M15 trend opposes entry direction

Calibration from live XAUUSD data 2026-08-10:
  - M5 ATR normal ~3.5 pts; vwap distance 1.7-2.9x ATR = overextended
  - M15 trend direction via last 2 candles (momentum_score too noisy single-candle)
"""
import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger("exhaustion_guard")

@dataclass
class ExhaustionVerdict:
    allowed: bool
    reason: str           # "" if allowed
    vwap_dist_atr: float  # |distance_to_vwap| / ATR for M5
    m15_trend: str        # "UP" | "DOWN" | "FLAT"
    m15_strength: float   # how many of last 3 M15 candles agree with trend

class ExhaustionGuard:
    VWAP_ATR_WARN = 1.5    # over this -> warn (reduce score, not block)
    VWAP_ATR_BLOCK = 2.0   # over this -> block entry
    M15_MIN_AGREE = 2      # at least 2 of last 3 M15 candles must agree

    def check(self, features: Any, candles: dict, direction: str) -> ExhaustionVerdict:
        """direction: 'BUY' | 'SELL' | 'WAIT'"""
        if direction not in ("BUY", "SELL"):
            return ExhaustionVerdict(True, "", 0.0, "FLAT", 0.0)

        # 1. M5 overextension vs VWAP
        vwap_dist = 0.0
        if hasattr(features, "distance_to_vwap") and isinstance(features.distance_to_vwap, dict):
            vwap_dist = float(features.distance_to_vwap.get("M5", 0.0))
        atr = 0.0
        if hasattr(features, "atr") and isinstance(features.atr, dict):
            atr = float(features.atr.get("M5", 0.0))
        atr_ratio = abs(vwap_dist) / atr if atr > 0 else 0.0

        # 2. M15 trend from last 3 candles
        m15_trend = "FLAT"
        m15_agree = 0.0
        m15 = (candles or {}).get("M15") or []
        if len(m15) >= 3:
            closes = [float(c["close"]) for c in m15[-3:]]
            ups = sum(1 for i in range(1, 3) if closes[i] > closes[i-1])
            downs = 3 - ups
            if ups >= self.M15_MIN_AGREE:
                m15_trend = "UP"
                m15_agree = ups
            elif downs >= self.M15_MIN_AGREE:
                m15_trend = "DOWN"
                m15_agree = downs

        # 3. Verdicts
        if direction == "BUY":
            if m15_trend == "DOWN":
                return ExhaustionVerdict(False, f"BUY vs M15 DOWN trend (agree={m15_agree:.0f}/3)", atr_ratio, m15_trend, m15_agree)
            if atr_ratio >= self.VWAP_ATR_BLOCK:
                return ExhaustionVerdict(False, f"BUY overextended {atr_ratio:.1f}x ATR above VWAP", atr_ratio, m15_trend, m15_agree)
            if atr_ratio >= self.VWAP_ATR_WARN:
                return ExhaustionVerdict(True, f"BUY warn {atr_ratio:.1f}x ATR (score penalty)", atr_ratio, m15_trend, m15_agree)

        elif direction == "SELL":
            if m15_trend == "UP":
                return ExhaustionVerdict(False, f"SELL vs M15 UP trend (agree={m15_agree:.0f}/3)", atr_ratio, m15_trend, m15_agree)
            if atr_ratio >= self.VWAP_ATR_BLOCK:
                return ExhaustionVerdict(False, f"SELL overextended {atr_ratio:.1f}x ATR below VWAP", atr_ratio, m15_trend, m15_agree)
            if atr_ratio >= self.VWAP_ATR_WARN:
                return ExhaustionVerdict(True, f"SELL warn {atr_ratio:.1f}x ATR (score penalty)", atr_ratio, m15_trend, m15_agree)

        return ExhaustionVerdict(True, "", atr_ratio, m15_trend, m15_agree)


if __name__ == "__main__":
    from types import SimpleNamespace
    g = ExhaustionGuard()

    # Case 1: BUY overextended above VWAP (2.87x) -> block
    feats = SimpleNamespace(
        distance_to_vwap={"M5": 10.0},
        atr={"M5": 3.5},
    )
    candles = {"M15": [{"close": 4335}, {"close": 4337}, {"close": 4339}]}  # M15 UP
    v = g.check(feats, candles, "BUY")
    assert not v.allowed and "overextended" in v.reason, f"Case1 fail: {v}"
    print(f"Case1 BUY overextended -> BLOCK: {v.reason}")

    # Case 2: SELL vs M15 UP -> block
    v2 = g.check(feats, candles, "SELL")
    assert not v2.allowed and "M15" in v2.reason, f"Case2 fail: {v2}"
    print(f"Case2 SELL vs M15 UP -> BLOCK: {v2.reason}")

    # Case 3: SELL aligned (M15 DOWN, price near VWAP) -> allow
    feats3 = SimpleNamespace(distance_to_vwap={"M5": -1.0}, atr={"M5": 3.5})
    candles3 = {"M15": [{"close": 4340}, {"close": 4338}, {"close": 4335}]}  # M15 DOWN
    v3 = g.check(feats3, candles3, "SELL")
    assert v3.allowed, f"Case3 fail: {v3}"
    print(f"Case3 SELL aligned -> ALLOW")

    # Case 4: BUY warn (1.7x) -> allowed with penalty
    feats4 = SimpleNamespace(distance_to_vwap={"M5": 6.0}, atr={"M5": 3.5})
    candles4 = {"M15": [{"close": 4335}, {"close": 4336}, {"close": 4338}]}  # M15 UP
    v4 = g.check(feats4, candles4, "BUY")
    assert v4.allowed and "warn" in v4.reason, f"Case4 fail: {v4}"
    print(f"Case4 BUY warn -> ALLOW with penalty: {v4.reason}")

    print("\nExhaustionGuard self-check OK: 4/4 pass")
