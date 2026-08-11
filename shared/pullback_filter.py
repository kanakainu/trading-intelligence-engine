"""Pullback Entry Filter — M5/M15 aligned pullback entries.

Filters out:
- BUY at M5/M15 local tops (no pullback)
- SELL at M5/M15 local bottoms (no pullback)
- Direction against M15 trend

Only allows:
- BUY on pullback in M15 UP trend (M5 price at/near support)
- SELL on pullback in M15 DOWN trend (M5 price at/near resistance)
"""
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger("pullback_filter")

@dataclass
class PullbackResult:
    allowed: bool
    reason: str
    m15_trend: str        # "UP" | "DOWN" | "FLAT"
    m5_pullback_ok: bool  # True if price pulled back enough
    pullback_pct: float   # How far from extreme (0-1)

class PullbackFilter:
    """
    Pullback Entry Filter for M5/M15.
    
    Logic:
    1. Detect M15 trend (last 5 candles)
    2. Detect M5 pullback depth vs recent range
    3. Allow entry only if:
       - M15 trend aligns with direction
       - M5 price pulled back at least 30% from extreme
    """
    
    M15_LOOKBACK = 3      # candles for M15 trend (was 5, faster response)
    M5_LOOKBACK = 20      # candles for M5 range
    MIN_PULLBACK = 0.3    # 30% pullback from extreme
    M15_MIN_AGREE = 2     # at least 2/3 candles same direction (was 3/5)
    
    def check(self, candles: dict, direction: str, current_price: float,
              regime: str = "", regime_strength: int = 0) -> PullbackResult:
        """
        candles: dict with M5, M15 candle lists [{"open", "high", "low", "close"}, ...]
        direction: "BUY" | "SELL"
        current_price: current bid/ask price
        """
        if direction not in ("BUY", "SELL"):
            return PullbackResult(False, "invalid_direction", "FLAT", False, 0.0)
        
        m15 = candles.get("M15", [])
        m5 = candles.get("M5", [])
        
        if len(m15) < self.M15_LOOKBACK or len(m5) < self.M5_LOOKBACK:
            return PullbackResult(False, "insufficient_candles", "FLAT", False, 0.0)
        
        # 1. M15 Trend Detection
        m15_closes = [float(c["close"]) for c in m15[-self.M15_LOOKBACK:]]
        ups = sum(1 for i in range(1, len(m15_closes)) if m15_closes[i] > m15_closes[i-1])
        downs = self.M15_LOOKBACK - 1 - ups
        
        if ups >= self.M15_MIN_AGREE:
            m15_trend = "UP"
        elif downs >= self.M15_MIN_AGREE:
            m15_trend = "DOWN"
        else:
            m15_trend = "FLAT"
        
        # 2. Check alignment
        # Opsi 2: bypass M15 FLAT if regime TRENDING strength >= 70, trend-following only
        trending_override = (str(regime).upper() == "TRENDING" and regime_strength >= 70)

        if direction == "BUY" and m15_trend != "UP":
            # Bypass only if TRENDING + M15 FLAT (not DOWN) — trend-following
            if not (trending_override and m15_trend == "FLAT"):
                return PullbackResult(False, f"BUY vs M15 {m15_trend}", m15_trend, False, 0.0)
        if direction == "SELL" and m15_trend != "DOWN":
            # SELL during TRENDING = counter-trend, NEVER bypass
            return PullbackResult(False, f"SELL vs M15 {m15_trend}", m15_trend, False, 0.0)
        
        # 3. M5 Pullback Check
        m5_highs = [float(c["high"]) for c in m5[-self.M5_LOOKBACK:]]
        m5_lows = [float(c["low"]) for c in m5[-self.M5_LOOKBACK:]]
        m5_range_high = max(m5_highs)
        m5_range_low = min(m5_lows)
        m5_range = m5_range_high - m5_range_low
        
        if m5_range == 0:
            return PullbackResult(False, "m5_range_zero", m15_trend, False, 0.0)
        
        if direction == "BUY":
            # Distance from M5 low (support) - want price near low
            dist_from_low = current_price - m5_range_low
            pullback_pct = dist_from_low / m5_range  # 0 = at low, 1 = at high
            # Allow if price pulled back to lower 40% of range (near support)
            m5_pullback_ok = pullback_pct <= 0.4
            reason = f"BUY pullback pct={pullback_pct:.2f} (need <=0.4)"
        else:  # SELL
            # Distance from M5 high (resistance) - want price near high
            dist_from_high = m5_range_high - current_price
            pullback_pct = dist_from_high / m5_range  # 0 = at high, 1 = at low
            # Allow if price pulled back to upper 40% of range (near resistance)
            m5_pullback_ok = pullback_pct <= 0.4
            reason = f"SELL pullback pct={pullback_pct:.2f} (need <=0.4)"
        
        if not m5_pullback_ok:
            # TRENDING regime bypass: M15 already confirmed, skip zone check
            if trending_override:
                return PullbackResult(True, f"{direction} trending_override (skip zone)", m15_trend, True, pullback_pct)
            return PullbackResult(False, reason, m15_trend, False, pullback_pct)
        
        return PullbackResult(True, reason, m15_trend, True, pullback_pct)


if __name__ == "__main__":
    # Self-test
    pf = PullbackFilter()
    
    # Create test candles: M15 UP trend, M5 in range
    m15_candles = [
        {"close": 4350}, {"close": 4352}, {"close": 4355}, 
        {"close": 4357}, {"close": 4360}  # UP trend
    ]
    m5_candles = []
    # M5 range: 4355 - 4365
    for i in range(20):
        m5_candles.append({"high": 4365, "low": 4355, "close": 4360})
    
    # Test BUY at 4358 (near low = 4355, pullback ~30%)
    candles = {"M15": m15_candles, "M5": m5_candles}
    r = pf.check(candles, "BUY", 4358.0)
    assert r.allowed, f"Expected allow, got {r.reason}"
    print(f"BUY at 4358: {r.allowed} - {r.reason}")
    
    # Test BUY at 4363 (near high = 4365, pullback ~80%) - should REJECT
    r2 = pf.check(candles, "BUY", 4363.0)
    assert not r2.allowed, f"Expected reject, got allow"
    print(f"BUY at 4363: {r2.allowed} - {r2.reason}")
    
    # Test SELL with M15 DOWN
    m15_down = [
        {"close": 4360}, {"close": 4357}, {"close": 4355},
        {"close": 4352}, {"close": 4350}
    ]
    r3 = pf.check({"M15": m15_down, "M5": m5_candles}, "SELL", 4362.0)
    assert r3.allowed, f"Expected allow, got {r3.reason}"
    print(f"SELL at 4362: {r3.allowed} - {r3.reason}")
    
    print("\nPullbackFilter self-check OK: 3/3 pass")