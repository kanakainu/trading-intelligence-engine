"""Pullback Filter v2 — Fibo Retracement + M5 Momentum.

Logic:
- Trend-following (M15 UP + BUY, M15 DOWN + SELL): allow directly
- Counter-trend (M15 DOWN + BUY, M15 UP + SELL):
    → Calc Fibo retrace from M15 swing H/L (last 20 candles)
    → Price in 50% / 61.8% / 78.6% zone (±tolerance)?
    → M5 last closed candle GAS toward direction (body > 0.3x ATR)?
    → Both YES → allow (counter-trend reversal confirmed)
    → Any NO → block
- M15 FLAT + regime TRENDING ≥70: allow trend-following direction
"""
from dataclasses import dataclass
import logging

logger = logging.getLogger("pullback_filter")

FIBO_LEVELS = [0.5, 0.618, 0.786]
FIBO_TOLERANCE = 0.015   # ±1.5% of swing range
M5_BODY_ATR_RATIO = 0.3  # M5 candle body must be >= 30% of ATR
M15_LOOKBACK = 20        # candles for swing H/L detection


@dataclass
class PullbackResult:
    allowed: bool
    reason: str
    m15_trend: str
    m5_pullback_ok: bool
    pullback_pct: float


def _swing(candles: list) -> tuple:
    """Return (swing_high, swing_low) from candle list."""
    highs = [float(c.get("high", 0)) for c in candles]
    lows  = [float(c.get("low", 0)) for c in candles]
    return max(highs), min(lows)


def _m15_trend(m15: list, lookback: int = 3) -> str:
    closes = [float(c["close"]) for c in m15[-lookback:]]
    ups = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
    downs = lookback - 1 - ups
    if ups >= lookback - 1:
        return "UP"
    if downs >= lookback - 1:
        return "DOWN"
    return "FLAT"


def _in_fibo_zone(price: float, swing_high: float, swing_low: float, direction: str) -> tuple:
    """Returns (in_zone: bool, level: float). BUY = retrace from high, SELL = retrace from low."""
    rng = swing_high - swing_low
    if rng <= 0:
        return False, 0.0
    for lvl in FIBO_LEVELS:
        if direction == "BUY":
            zone = swing_high - rng * lvl
        else:
            zone = swing_low + rng * lvl
        if abs(price - zone) <= rng * FIBO_TOLERANCE:
            return True, lvl
    return False, 0.0


def _m5_gas(m5: list, direction: str, atr: float) -> bool:
    """Last closed M5 candle body > 0.3x ATR and confirms direction."""
    if len(m5) < 2:
        return True  # no data = pass
    c = m5[-2]
    o, cl = float(c.get("open", 0)), float(c.get("close", 0))
    body = abs(cl - o)
    if atr > 0 and body < atr * M5_BODY_ATR_RATIO:
        return False
    if direction == "BUY" and cl <= o:
        return False
    if direction == "SELL" and cl >= o:
        return False
    return True


class PullbackFilter:
    def check(self, candles: dict, direction: str, current_price: float,
              regime: str = "", regime_strength: int = 0,
              features=None) -> PullbackResult:

        if direction not in ("BUY", "SELL"):
            return PullbackResult(False, "invalid_direction", "FLAT", False, 0.0)

        m15 = candles.get("M15", [])
        m5  = candles.get("M5", [])

        if len(m15) < 3:
            return PullbackResult(True, "no_m15_data_pass", "FLAT", True, 0.5)

        # Regime conflict guard: block counter-regime entries
        if regime and regime_strength:
            if str(regime).upper() == "TRENDING" and regime_strength >= 80:
                if direction == "SELL":
                    return PullbackResult(False,
                        f"regime_conflict TRENDING={regime_strength} blocks SELL",
                        "UP", False, 0.5)
                if direction == "BUY" and regime_strength >= 90:
                    pass  # BUY in strong TRENDING = ok

        # EMA20 phase filter: expansion/accumulation/distribution
        ema20 = features.get_ema("M5", 20) if features and hasattr(features, "get_ema") else None
        if ema20 and ema20 > 0:
            dist_pct = (current_price - ema20) / ema20 * 100
            # Expansion UP (>0.15%) → block SELL
            if dist_pct > 0.15 and direction == "SELL":
                return PullbackResult(False,
                    f"ema20_expansion_up dist={dist_pct:.2f}% blocks SELL",
                    "UP", False, 0.5)
            # Expansion DOWN (<-0.15%) → block BUY
            elif dist_pct < -0.15 and direction == "BUY":
                return PullbackResult(False,
                    f"ema20_expansion_down dist={dist_pct:.2f}% blocks BUY",
                    "DOWN", False, 0.5)
            # Accumulation/Distribution zone (±0.15%) → both ok

        trend = _m15_trend(m15)

        # ATR for M5 momentum check
        atr = 0.0
        if features and hasattr(features, "atr") and isinstance(features.atr, dict):
            atr = float(features.atr.get("M5", 0.0))

        # Trend-following
        is_trend = (trend == "UP" and direction == "BUY") or \
                   (trend == "DOWN" and direction == "SELL")
        # FLAT regime override
        if trend == "FLAT":
            trending_override = str(regime).upper() == "TRENDING" and regime_strength >= 70
            if trending_override:
                is_trend = True
            else:
                return PullbackResult(False, f"m15_flat_no_trend regime={regime} str={regime_strength}",
                                      "FLAT", False, 0.5)

        if is_trend:
            # Trend-following: just check M5 gas
            gas_ok = _m5_gas(m5, direction, atr)
            if not gas_ok:
                return PullbackResult(False, f"m5_weak_trend dir={direction}", trend, False, 0.5)
            return PullbackResult(True, f"trend_follow_{trend}_m5_gas_ok", trend, True, 0.5)

        # Counter-trend: need Fibo zone + M5 gas
        m15_slice = m15[-M15_LOOKBACK:] if len(m15) >= M15_LOOKBACK else m15
        sw_high, sw_low = _swing(m15_slice)
        in_zone, fibo_lvl = _in_fibo_zone(current_price, sw_high, sw_low, direction)

        if not in_zone:
            rng = sw_high - sw_low
            pct = (current_price - sw_low) / rng if rng > 0 else 0.5
            return PullbackResult(False,
                f"counter_trend_not_in_fibo dir={direction} m15={trend} price={current_price:.2f} H={sw_high:.2f} L={sw_low:.2f}",
                trend, False, pct)

        gas_ok = _m5_gas(m5, direction, atr)
        if not gas_ok:
            return PullbackResult(False,
                f"counter_trend_fibo{fibo_lvl:.3f}_m5_weak dir={direction}",
                trend, False, fibo_lvl)

        return PullbackResult(True,
            f"counter_trend_fibo{fibo_lvl:.3f}_m5_gas_ok dir={direction} m15={trend}",
            trend, True, fibo_lvl)
