"""
RiriScalps v1.0 — Unified XAUUSD Scalping Strategy
Replaces: SemiHFT + Aggressive

LAYER 0 — Volatility Regime Guard
LAYER 1 — Spread Trap Guard
LAYER 2 — Signal Engine (3 engines, priority order)
  ENGINE A: 2-Bar VWAP Reversal (|Z|>=1.5 + 2 consecutive M5 reversal candles)
  ENGINE B: Swing Break + Retest (M5 close > swing_high/low + retest 1-3 bars)
  ENGINE C: Wick Rejection at Key Level (wick > 2x body at swing pivot)
LAYER 3 — Tick Microstructure Confirm (non-blocking if unavailable)
"""
import uuid
import logging
from typing import Optional, Tuple

from core.strategy.base_strategy import BaseStrategy
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.strategy.strategy_metadata import StrategyMetadata
from core.signals.signal import Signal, Direction
from shared.market_context import Regime

logger = logging.getLogger("RiriScalps")

SWING_LOOKBACK   = 10
RETEST_MAX_BARS  = 4       # was 3 — give price more time to retest
RETEST_TOL_ATR   = 0.20   # retest tolerance = 20% of ATR (dynamic, was fixed 0.30 pts)
WICK_BODY_RATIO  = 2.0    # stricter: wick must be 2x body
SPREAD_Z_MAX     = 2.0    # spread z-score block threshold
ATR_VOL_HIGH     = 2.0    # ATR > 2x avg = high vol → tighten
ATR_VOL_THIN     = 0.5    # ATR < 0.5x avg = thin → skip
ENG_C_PROXIMITY  = 0.5    # tighter: price within 0.5*ATR of swing level

# Module-level state machine for Engine B (swing break retest)
_breakout_state: dict = {}


def _swing_levels(candles: list, lookback: int) -> Tuple[float, float]:
    recent = candles[-lookback-2:-2]  # exclude last 2 so breakout candle can exceed
    if not recent:
        return 0.0, 999999.0
    return (max(float(c.get("high", 0)) for c in recent),
            min(float(c.get("low", 0)) for c in recent))


def _swing_pivot_sl(candles: list, direction: str, lookback: int = 10) -> Optional[float]:
    recent = candles[-lookback-1:-1]
    if not recent:
        return None
    return (min(float(c.get("low", 0)) for c in recent) if direction == "BUY"
            else max(float(c.get("high", 0)) for c in recent))


class RiriScalpsStrategy(BaseStrategy):
    def __init__(self):
        meta = StrategyMetadata(
            id="riri_scalps_v1",
            name="RiriScalps",
            version="1.0.0",
            priority=90,
            author="Riri",
            description="Unified XAUUSD scalping: 2-Bar VWAP Rev + Swing Retest + Wick Rejection"
        )
        super().__init__(meta)
        self._atr_history: list = []  # rolling ATR for vol regime

    def initialize(self) -> None:
        self._initialized = True

    def observe(self, context: StrategyContext) -> None:
        pass

    def analyze(self, context: StrategyContext) -> StrategyResult:
        market_ctx = context.scan.market
        candles_m5 = context.scan.features.candles.get("M5", [])
        sym = "XAUUSD"

        if not candles_m5 or len(candles_m5) < SWING_LOOKBACK + 2:
            return StrategyResult(signal=None, confidence=0.0, reason="insufficient_m5_data")

        price    = market_ctx.price
        z        = market_ctx.vwap_z_score
        atr      = market_ctx.atr
        spread   = getattr(market_ctx, "spread", 0.0)
        regime   = getattr(market_ctx, "regime", "UNKNOWN")
        strength = getattr(market_ctx, "regime_strength", 0)

        last = candles_m5[-2]  # last CLOSED candle
        prev = candles_m5[-3]  # one before last

        # ── LAYER 0: Volatility Regime Guard ─────────────────────────────
        self._atr_history.append(atr)
        if len(self._atr_history) > 20:
            self._atr_history.pop(0)
        atr_avg = sum(self._atr_history) / len(self._atr_history)

        if atr_avg > 0:
            atr_ratio = atr / atr_avg
            if atr_ratio < ATR_VOL_THIN:
                return StrategyResult(signal=None, confidence=0.0,
                                      reason=f"thin_market atr_ratio={atr_ratio:.2f}")
            # High vol: tighten Z threshold to 2.0
            z_threshold = 2.0 if atr_ratio > ATR_VOL_HIGH else 1.5
        else:
            z_threshold = 1.5

        # ── LAYER 1: Spread Trap Guard ────────────────────────────────────
        # Use simple spread check: if spread > 0.5 pts on XAUUSD, skip
        if spread > 0.5:
            return StrategyResult(signal=None, confidence=0.0,
                                  reason=f"spread_trap spread={spread:.2f}")

        # ─────────────────────────────────────────────────────────────────
        # ENGINE A: 2-Bar VWAP Reversal
        # ─────────────────────────────────────────────────────────────────
        if abs(z) >= z_threshold:
            c1 = candles_m5[-3]
            c2 = candles_m5[-2]
            c1_body = abs(c1["close"] - c1["open"])
            c2_body = abs(c2["close"] - c2["open"])
            valid_body = c1_body > 0.10 and c2_body > 0.10
            _a_key = f"{sym}_{c1['close']:.2f}_{c2['close']:.2f}"
            if _a_key == getattr(self, "_last_engA_key", None):
                pass  # same candle pair — skip Engine A, fall through to B/C
            elif z < -z_threshold:
                # Oversold → BUY: skip if strong downtrend (regime likely continues)
                if (regime not in (Regime.TRENDING_BEAR,) or strength < 85) and (
                        c1["close"] > c1["open"] and c2["close"] > c2["open"]
                        and c2["close"] > c1["close"] and valid_body):
                    self._last_engA_key = _a_key
                    sig_dir = Direction.BUY
                    reason  = f"A_2bar_vwap_rev_buy z={z:.2f}"
                    conf    = min(0.88, 0.72 + (abs(z) - z_threshold) * 0.08)
                    sl      = _swing_pivot_sl(candles_m5, "BUY") or (price - atr * 0.5)
                    tp      = price + abs(price - sl) * 1.5
                    return self._emit(sym, sig_dir, price, conf, reason, sl, tp, z, str(regime))

            elif z > z_threshold:
                # Overbought → SELL: skip if strong uptrend
                if (regime not in (Regime.TRENDING_BULL,) or strength < 85) and (
                        c1["close"] < c1["open"] and c2["close"] < c2["open"]
                        and c2["close"] < c1["close"] and valid_body):
                    self._last_engA_key = _a_key
                    sig_dir = Direction.SELL
                    reason  = f"A_2bar_vwap_rev_sell z={z:.2f}"
                    conf    = min(0.88, 0.72 + (abs(z) - z_threshold) * 0.08)
                    sl      = _swing_pivot_sl(candles_m5, "SELL") or (price + atr * 0.5)
                    tp      = price - abs(sl - price) * 1.5
                    return self._emit(sym, sig_dir, price, conf, reason, sl, tp, z, str(regime))

        # ─────────────────────────────────────────────────────────────────
        # ENGINE B: Swing Break + Retest
        # ─────────────────────────────────────────────────────────────────
        swing_high, swing_low = _swing_levels(candles_m5, SWING_LOOKBACK)
        last_c   = candles_m5[-2]
        lc_close = float(last_c.get("close", 0))
        lc_open  = float(last_c.get("open",  0))
        lc_body  = abs(lc_close - lc_open)
        min_body = max(0.20, atr * 0.20)

        logger.info(f"[RIRI] EngB scan: close={lc_close:.2f} sh={swing_high:.2f} sl={swing_low:.2f} body={lc_body:.2f} min={min_body:.2f} pending={_breakout_state.get(sym)}")

        # Detect new breakout
        if lc_close > swing_high and lc_body >= min_body:
            _breakout_state[sym] = {"direction": "BUY", "level": swing_high, "bars": 0}
            logger.info(f"[RIRI] Engine B: breakout BUY level={swing_high:.2f}")
        elif lc_close < swing_low and lc_body >= min_body:
            _breakout_state[sym] = {"direction": "SELL", "level": swing_low, "bars": 0}
            logger.info(f"[RIRI] Engine B: breakout SELL level={swing_low:.2f}")
        elif sym in _breakout_state:
            # Check retest
            state = _breakout_state[sym]
            state["bars"] += 1
            if state["bars"] > RETEST_MAX_BARS:
                del _breakout_state[sym]
            elif abs(price - state["level"]) <= atr * RETEST_TOL_ATR:
                direction = state["direction"]
                level     = state["level"]
                sig_dir   = Direction.BUY if direction == "BUY" else Direction.SELL
                sl  = (level - atr * 0.5) if direction == "BUY" else (level + atr * 0.5)
                tp  = (price + abs(price - sl) * 2.0) if direction == "BUY" else (price - abs(sl - price) * 2.0)
                conf = min(0.85, 0.75 + state["bars"] * 0.03)
                reason = f"B_swing_retest_{direction} level={level:.2f} bars={state['bars']}"
                del _breakout_state[sym]
                return self._emit(sym, sig_dir, price, conf, reason, sl, tp, z, str(regime))

        # ─────────────────────────────────────────────────────────────────
        # ENGINE C: Wick Rejection at Key Level
        # ─────────────────────────────────────────────────────────────────
        lc_high  = float(last_c.get("high", 0))
        lc_low   = float(last_c.get("low", 0))
        upper_wick = lc_high - max(lc_close, lc_open)
        lower_wick = min(lc_close, lc_open) - lc_low

        if lc_body > 0:
            logger.info(f"[RIRI] EngC scan: lower_wick={lower_wick:.2f} upper_wick={upper_wick:.2f} body={lc_body:.2f} ratio={WICK_BODY_RATIO} price={price:.2f} sh={swing_high:.2f} sl={swing_low:.2f} prox={ENG_C_PROXIMITY}*atr={ENG_C_PROXIMITY*atr:.2f}")
            _c_key = f"{sym}_{lc_high:.2f}_{lc_low:.2f}_{lc_close:.2f}"
            if _c_key == getattr(self, "_last_engC_key", None):
                return StrategyResult(signal=None, confidence=0.0, reason="engC_same_candle")
            self._last_engC_key = _c_key  # mark BEFORE signal check — fire once per candle max
            # Bullish wick rejection: long lower wick, close near high → BUY
            if (lower_wick > WICK_BODY_RATIO * lc_body
                    and lc_close > lc_open
                    and abs(price - swing_low) <= ENG_C_PROXIMITY * atr):
                self._last_engC_key = _c_key
                sig_dir = Direction.BUY
                reason  = f"C_wick_reject_buy wick={lower_wick:.2f} body={lc_body:.2f}"
                conf    = 0.80
                sl      = lc_low - 0.1
                tp      = price + abs(price - sl) * 1.5
                return self._emit(sym, sig_dir, price, conf, reason, sl, tp, z, str(regime))

            # Bearish wick rejection: long upper wick, close near low → SELL
            if (upper_wick > WICK_BODY_RATIO * lc_body
                    and lc_close < lc_open
                    and abs(price - swing_high) <= ENG_C_PROXIMITY * atr):
                self._last_engC_key = _c_key
                sig_dir = Direction.SELL
                reason  = f"C_wick_reject_sell wick={upper_wick:.2f} body={lc_body:.2f}"
                conf    = 0.80
                sl      = lc_high + 0.1
                tp      = price - abs(sl - price) * 1.5
                return self._emit(sym, sig_dir, price, conf, reason, sl, tp, z, str(regime))

        return StrategyResult(signal=None, confidence=0.0, reason="no_setup")

    def _emit(self, sym, sig_dir, price, conf, reason, sl, tp, z, regime) -> StrategyResult:
        logger.info(f"[RIRI] ENTRY: {sig_dir} {reason} sl={sl:.2f} tp={tp:.2f} conf={conf:.0%}")
        signal = Signal(
            signal_id=str(uuid.uuid4()),
            strategy=self.id,
            symbol=sym,
            direction=sig_dir,
            entry_zone={"price": price, "high": price + 0.5, "low": price - 0.5},
            confidence=conf,
            timeframe="M5"
        )
        return StrategyResult(
            signal=signal,
            confidence=conf,
            reason=reason,
            metadata={
                "z_score":    z,
                "regime":     regime,
                "setup_type": reason.split("_")[0],
                "sl":         sl,
                "tp":         tp,
            }
        )

    def shutdown(self) -> None:
        self._initialized = False
        _breakout_state.clear()
