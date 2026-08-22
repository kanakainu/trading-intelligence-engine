"""SetupDetector — structural setup detection (M5/M15).
No setup = NO TRADE. High score without setup = still NO TRADE.
"""
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict
from shared.market_context import MarketContext, Regime


class SetupType(str, Enum):
    TREND_PULLBACK            = "TREND_PULLBACK"
    LIQUIDITY_SWEEP_REVERSAL  = "LIQUIDITY_SWEEP_REVERSAL"
    BREAKOUT_RETEST           = "BREAKOUT_RETEST"
    RANGE_EDGE                = "RANGE_EDGE"
    MOMENTUM_BREAK            = "MOMENTUM_BREAK"
    NONE                      = "NONE"


class SetupDirection(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"
    NONE = "NONE"


def _get(c: Dict, *keys, default=0.0) -> float:
    for k in keys:
        v = c.get(k)
        if v is not None:
            try: return float(v)
            except (ValueError, TypeError): pass
    return default


@dataclass
class Setup:
    type:       SetupType
    direction:  SetupDirection
    quality:    float
    reason:     str
    zone_price: float

    @property
    def is_valid(self) -> bool:
        return self.type != SetupType.NONE


def _no_setup(reason: str = "") -> Setup:
    return Setup(SetupType.NONE, SetupDirection.NONE, 0.0, reason, 0.0)


def detect(
    ctx:           MarketContext,
    candles_m5:    List[Dict],
    candles_m1:    List[Dict],
    current_price: float,
) -> Setup:
    atr = ctx.atr
    if atr <= 0 or not candles_m5:
        return _no_setup("no_atr_or_candles")

    cs5 = [c for c in candles_m5[-20:] if c]
    if len(cs5) < 5:
        return _no_setup("insufficient_m5_candles")

    highs  = [_get(c, "high",  "High")  for c in cs5]
    lows   = [_get(c, "low",   "Low")   for c in cs5]
    closes = [_get(c, "close", "Close") for c in cs5]

    recent_high = max(highs[-6:])
    recent_low  = min(lows[-6:])
    prev_high   = max(highs[-12:-6]) if len(highs) >= 12 else recent_high
    prev_low    = min(lows[-12:-6])  if len(lows)  >= 12 else recent_low

    # 1. TREND_PULLBACK
    if ctx.regime in (Regime.TRENDING_BULL, Regime.TRENDING_BEAR):
        if ctx.regime == Regime.TRENDING_BULL:
            dist = current_price - recent_low
            if -0.2 * atr <= dist <= 1.5 * atr:
                return Setup(SetupType.TREND_PULLBACK, SetupDirection.BUY,
                             25.0, f"bull_pullback_swing={recent_low:.2f}", recent_low)
        else:
            dist = recent_high - current_price
            if -0.2 * atr <= dist <= 1.5 * atr:
                return Setup(SetupType.TREND_PULLBACK, SetupDirection.SELL,
                             25.0, f"bear_pullback_swing={recent_high:.2f}", recent_high)

    # 2. LIQUIDITY_SWEEP_REVERSAL
    last_close = closes[-1] if closes else current_price
    last_low   = lows[-1]   if lows   else current_price
    last_high  = highs[-1]  if highs  else current_price

    if (last_low < recent_low) and ((recent_low - last_low) < 0.5 * atr) and (last_close > recent_low):
        return Setup(SetupType.LIQUIDITY_SWEEP_REVERSAL, SetupDirection.BUY,
                     28.0, f"liq_sweep_buy={recent_low:.2f}", recent_low)
    if (last_high > recent_high) and ((last_high - recent_high) < 0.5 * atr) and (last_close < recent_high):
        return Setup(SetupType.LIQUIDITY_SWEEP_REVERSAL, SetupDirection.SELL,
                     28.0, f"liq_sweep_sell={recent_high:.2f}", recent_high)

    # 3. BREAKOUT_RETEST
    # Don't signal breakout retest if Z-score shows extreme mean reversion territory
    vwap_z = getattr(ctx, 'vwap_z_score', 0.0)
    if abs(vwap_z) < 2.0:  # Only allow breakout retest when not in extreme MR zone
        if recent_high > prev_high + 0.5 * atr:
            dist = current_price - prev_high
            if 0 <= dist <= 0.3 * atr:
                return Setup(SetupType.BREAKOUT_RETEST, SetupDirection.BUY,
                             22.0, f"breakout_retest_buy={prev_high:.2f}", prev_high)
        if recent_low < prev_low - 0.5 * atr:
            dist = prev_low - current_price
            if 0 <= dist <= 0.3 * atr:
                return Setup(SetupType.BREAKOUT_RETEST, SetupDirection.SELL,
                             22.0, f"breakout_retest_sell={prev_low:.2f}", prev_low)

    # 4. RANGE_EDGE
    if ctx.regime == Regime.RANGING:
        if (current_price - recent_low) <= 1.0 * atr:
            return Setup(SetupType.RANGE_EDGE, SetupDirection.BUY,
                         20.0, f"range_edge_buy={recent_low:.2f}", recent_low)
        if (recent_high - current_price) <= 1.0 * atr:
            return Setup(SetupType.RANGE_EDGE, SetupDirection.SELL,
                         20.0, f"range_edge_sell={recent_high:.2f}", recent_high)

    # 5. MOMENTUM_BREAK (Refined for Aggressive/SemiHFT)
    # Quality validation: body strength, directional consistency, breakout location
    
    # Check M1 for fast breakout
    m1_last = candles_m1[-1]
    m1_body = abs(m1_last['close'] - m1_last['open'])
    m1_atr = atr / 5.0  # Proxy M1 ATR from M5 ATR
    m1_spike = m1_body > 1.2 * m1_atr
    
    # Analyze breakout candle (last M5 candle)
    last_high = highs[-1]
    last_low = lows[-1]
    last_close = closes[-1]
    last_open = _get(cs5[-1], "open", "Open")
    last_body = abs(last_close - last_open)
    
    # Directional consistency: last 3 candles same direction
    dir_consistency = 0
    for i in range(-3, 0):
        if i + len(cs5) >= 0:
            c = cs5[i]
            c_close = _get(c, "close", "Close")
            c_open = _get(c, "open", "Open")
            if c_close > c_open: dir_consistency += 1
            elif c_close < c_open: dir_consistency -= 1
    
    body_strength = last_body / atr if atr > 0 else 0
    
    # BUY breakout: price > recent_high OR M1 spike at high
    if current_price > recent_high or (current_price > last_high and m1_spike):
        quality = 12.0  # Lowered base from 15
        if body_strength >= 0.4: quality += 8.0  # Lowered from 0.5/10
        if dir_consistency >= 2: quality += 10.0
        if m1_spike: quality += 5.0
        
        return Setup(SetupType.MOMENTUM_BREAK, SetupDirection.BUY,
                     max(5.0, quality), 
                     f"fast_break_up_q={quality:.1f}", 
                     recent_high)
    
    # SELL breakdown: price < recent_low OR M1 spike at low
    if current_price < recent_low or (current_price < last_low and m1_spike):
        quality = 12.0
        if body_strength >= 0.4: quality += 8.0
        if dir_consistency <= -2: quality += 10.0
        if m1_spike: quality += 5.0
        
        return Setup(SetupType.MOMENTUM_BREAK, SetupDirection.SELL,
                     max(5.0, quality),
                     f"fast_break_down_q={quality:.1f}",
                     recent_low)

    return _no_setup("no_structural_setup")
