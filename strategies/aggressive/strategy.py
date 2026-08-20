"""
AggressiveStrategy v5.0 — M5 Swing Break + Retest

Entry logic (REFACTORED):
  1. ENGINE A: Swing Break Detection — M5 candle closes ABOVE swing_high (last 10 bars) or BELOW swing_low
  2. ENGINE B: Retest Entry — After breakout detected, wait 1-2 M5 candles retesting the broken level
  3. Entry at retest (better price), not at breakout candle

M5 signal source only. M1 removed.
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

logger = logging.getLogger("AggressiveStrategy")

# State machine: track pending breakout for retest confirmation
# {symbol: {"direction": "BUY"/"SELL", "level": float, "bars_waited": int}}
_breakout_state: dict = {}

RETEST_MAX_BARS = 3      # wait max 3 M5 bars for retest
RETEST_TOLERANCE = 0.30  # price must come within 0.30 pts of broken level
SWING_LOOKBACK = 10      # bars for swing high/low detection


def _find_swing_levels(candles: list, lookback: int) -> Tuple[float, float]:
    """Find swing high and swing low of last N closed candles."""
    recent = candles[-lookback-1:-1]  # exclude current forming candle
    if not recent:
        return 0.0, 999999.0
    swing_high = max(float(c.get("high", 0)) for c in recent)
    swing_low  = min(float(c.get("low",  0)) for c in recent)
    return swing_high, swing_low


def _is_breakout_candle(candle: dict, swing_high: float, swing_low: float, atr: float) -> Optional[str]:
    """Check if candle breaks swing level with meaningful body."""
    close = float(candle.get("close", 0))
    open_ = float(candle.get("open",  0))
    body  = abs(close - open_)

    min_body = max(0.20, atr * 0.20)  # at least 0.20 pts or 20% ATR

    if close > swing_high and body >= min_body:
        return "BUY"
    if close < swing_low and body >= min_body:
        return "SELL"
    return None


def _is_retest(price: float, level: float, direction: str) -> bool:
    """Price has pulled back to within RETEST_TOLERANCE of broken level."""
    return abs(price - level) <= RETEST_TOLERANCE


class AggressiveStrategy(BaseStrategy):
    def __init__(self):
        meta = StrategyMetadata(
            id="aggressive_v1",
            name="Aggressive Swing Break+Retest",
            version="5.0.0",
            priority=80,
            author="Riri",
            description="M5 Swing Break detection + Retest entry (not breakout candle)"
        )
        super().__init__(meta)

    def initialize(self) -> None:
        self._initialized = True

    def observe(self, context: StrategyContext) -> None:
        pass

    def analyze(self, context: StrategyContext) -> StrategyResult:
        market_ctx  = context.scan.market
        candles_m5  = context.scan.features.candles.get("M5", [])
        sym         = "XAUUSD"

        if not candles_m5 or len(candles_m5) < SWING_LOOKBACK + 2:
            return StrategyResult(signal=None, confidence=0.0, reason="insufficient_m5_data")

        price    = market_ctx.price
        atr      = market_ctx.atr
        z        = market_ctx.vwap_z_score
        regime   = getattr(market_ctx, "regime", "UNKNOWN")
        strength = getattr(market_ctx, "regime_strength", 0)

        last_closed = candles_m5[-2]  # last fully closed M5 candle

        swing_high, swing_low = _find_swing_levels(candles_m5, SWING_LOOKBACK)

        # ── ENGINE A: Detect new breakout ─────────────────────────────────
        breakout_dir = _is_breakout_candle(last_closed, swing_high, swing_low, atr)
        if breakout_dir:
            broken_level = swing_high if breakout_dir == "BUY" else swing_low
            _breakout_state[sym] = {
                "direction":   breakout_dir,
                "level":       broken_level,
                "bars_waited": 0,
            }
            logger.info(f"[AGGR] Breakout detected: {breakout_dir} level={broken_level:.2f}")
            # Do NOT enter here — wait for retest
            return StrategyResult(signal=None, confidence=0.0,
                                  reason=f"breakout_detected_{breakout_dir}_wait_retest level={broken_level:.2f}")

        # ── ENGINE B: Check for retest of pending breakout ────────────────
        state = _breakout_state.get(sym)
        if state:
            state["bars_waited"] += 1

            # Expire state if too many bars passed
            if state["bars_waited"] > RETEST_MAX_BARS:
                logger.info(f"[AGGR] Retest expired after {state['bars_waited']} bars")
                del _breakout_state[sym]
                return StrategyResult(signal=None, confidence=0.0, reason="retest_expired")

            direction = state["direction"]
            level     = state["level"]

            if _is_retest(price, level, direction):
                # Retest confirmed — enter in breakout direction
                # SL: just beyond the retest level
                if direction == "BUY":
                    sl = level - atr * 0.5
                    tp = price + abs(price - sl) * 2.0
                    sig_dir = Direction.BUY
                else:
                    sl = level + atr * 0.5
                    tp = price - abs(sl - price) * 2.0
                    sig_dir = Direction.SELL

                confidence = min(0.85, 0.75 + (state["bars_waited"] * 0.03))
                reason = f"retest_{direction}_level={level:.2f}_bars={state['bars_waited']}"

                logger.info(f"[AGGR] ENTRY: {sig_dir} {reason} sl={sl:.2f} tp={tp:.2f}")
                del _breakout_state[sym]  # clear state after entry

                signal = Signal(
                    signal_id=str(uuid.uuid4()),
                    strategy=self.id,
                    symbol=sym,
                    direction=sig_dir,
                    entry_zone={"price": price, "high": price + 0.5, "low": price - 0.5},
                    confidence=confidence,
                    timeframe="M5"
                )
                return StrategyResult(
                    signal=signal,
                    confidence=confidence,
                    reason=reason,
                    metadata={
                        "z_score":    z,
                        "regime":     str(regime),
                        "setup_type": "SWING_BREAK_RETEST",
                        "sl":         sl,
                        "tp":         tp,
                        "level":      level,
                    }
                )

        return StrategyResult(signal=None, confidence=0.0, reason="no_momentum_break")

    def shutdown(self) -> None:
        self._initialized = False
        _breakout_state.clear()
