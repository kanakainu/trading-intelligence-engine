"""
SemiHFT v4.0 — 2-Bar Reversal at VWAP Band

Entry logic (REFACTORED — not filter loosening):
  1. Price must be OUTSIDE 1.5×ATR from VWAP (extreme zone)
  2. Need 2 CONSECUTIVE M5 candles confirming reversal direction
  3. SL at nearest M5 swing pivot (not flat ATR)

Signal source: M5 candles. M1 removed (too noisy for XAUUSD).
"""
import uuid
import logging
from typing import Optional

from core.strategy.base_strategy import BaseStrategy
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.strategy.strategy_metadata import StrategyMetadata
from core.signals.signal import Signal, Direction
from shared.market_context import Regime

logger = logging.getLogger("SemiHFTStrategy")


def _swing_pivot_sl(candles_m5: list, direction: str, lookback: int = 10) -> Optional[float]:
    """SL at nearest M5 swing pivot — not flat ATR."""
    recent = candles_m5[-lookback-1:-1] if len(candles_m5) > lookback else candles_m5[:-1]
    if not recent:
        return None
    if direction == "BUY":
        return min(float(c.get("low", 0)) for c in recent)
    return max(float(c.get("high", 0)) for c in recent)


class SemiHFTStrategy(BaseStrategy):
    def __init__(self):
        meta = StrategyMetadata(
            id="semi_hft_c8_v4",
            name="SemiHFT 2-Bar Reversal",
            version="4.0.0",
            priority=90,
            author="Riri",
            description="2 consecutive M5 reversal candles outside 1.5xATR VWAP band"
        )
        super().__init__(meta)

    def initialize(self) -> None:
        self._initialized = True

    def observe(self, context: StrategyContext) -> None:
        pass

    def analyze(self, context: StrategyContext) -> StrategyResult:
        market_ctx = context.scan.market
        candles_m5 = context.scan.features.candles.get("M5", [])

        if not candles_m5 or len(candles_m5) < 4:
            return StrategyResult(signal=None, confidence=0.0, reason="insufficient_m5_data")

        price    = market_ctx.price
        z        = market_ctx.vwap_z_score
        atr      = market_ctx.atr
        vwap     = getattr(market_ctx, "vwap", None) or price
        regime   = getattr(market_ctx, "regime", "UNKNOWN")
        strength = getattr(market_ctx, "regime_strength", 0)

        # Block very strong trends — MR doesn't work there
        if regime in (Regime.TRENDING_BULL, Regime.TRENDING_BEAR) and strength > 85:
            return StrategyResult(signal=None, confidence=0.0, reason=f"strong_trend_{strength}")

        # ── CONDITION 1: Z-score must be extreme (|Z| >= 1.5) ──────────────
        # vwap field not available in context — use Z-score as proxy
        # Z = (price - vwap) / std_dev, so |Z| >= 1.5 ≈ price outside 1.5×stddev from VWAP
        if abs(z) < 1.5:
            return StrategyResult(
                signal=None, confidence=0.0,
                reason=f"not_extreme_zone z={z:.2f} need=|z|>=1.5"
            )

        # ── CONDITION 2: 2 consecutive M5 candles confirm reversal ────────
        c1 = candles_m5[-3]  # 2 candles ago (older)
        c2 = candles_m5[-2]  # 1 candle ago (newer, closed)
        # current c0 = candles_m5[-1] (forming — not used for signal)

        signal_dir = None
        reason     = "no_2bar_reversal"
        confidence = 0.0

        if z < -1.5:
            # Oversold region — look for BUY reversal
            # Both c1 and c2 must be bullish AND c2 close > c1 close (progressive)
            c1_bull = c1["close"] > c1["open"]
            c2_bull = c2["close"] > c2["open"]
            progressive = c2["close"] > c1["close"]
            c1_body = abs(c1["close"] - c1["open"])
            c2_body = abs(c2["close"] - c2["open"])
            valid_body = c1_body > 0.10 and c2_body > 0.10

            if c1_bull and c2_bull and progressive and valid_body:
                signal_dir = Direction.BUY
                reason = f"2bar_rev_buy z={z:.2f}"
                confidence = min(0.88, 0.72 + (abs(z) - 1.5) * 0.08)

        elif z > 1.5:
            # Overbought region — look for SELL reversal
            c1_bear = c1["close"] < c1["open"]
            c2_bear = c2["close"] < c2["open"]
            progressive = c2["close"] < c1["close"]
            c1_body = abs(c1["close"] - c1["open"])
            c2_body = abs(c2["close"] - c2["open"])
            valid_body = c1_body > 0.10 and c2_body > 0.10

            if c1_bear and c2_bear and progressive and valid_body:
                signal_dir = Direction.SELL
                reason = f"2bar_rev_sell z={z:.2f}"
                confidence = min(0.88, 0.72 + (abs(z) - 1.5) * 0.08)

        if not signal_dir:
            return StrategyResult(signal=None, confidence=0.0, reason=reason)

        # ── SL: nearest M5 swing pivot (not flat ATR) ─────────────────────
        sl_pivot = _swing_pivot_sl(candles_m5, signal_dir.value, lookback=10)
        sl = sl_pivot if sl_pivot else (price - atr * 0.5 if signal_dir == Direction.BUY else price + atr * 0.5)
        tp = price + abs(price - sl) * 1.5 if signal_dir == Direction.BUY else price - abs(sl - price) * 1.5

        logger.info(f"[SEMIHFT] ENTRY: {signal_dir} {reason} sl={sl:.2f} tp={tp:.2f}")

        signal = Signal(
            signal_id=str(uuid.uuid4()),
            strategy=self.id,
            symbol="XAUUSD",
            direction=signal_dir,
            entry_zone={"price": price, "high": price + 0.5, "low": price - 0.5},
            confidence=confidence,
            timeframe="M5"
        )
        return StrategyResult(
            signal=signal,
            confidence=confidence,
            reason=reason,
            metadata={
                "z_score": z,
                "regime": str(regime),
                "setup_type": "2BAR_VWAP_REVERSAL",
                "sl": sl,
                "tp": tp,
                "abs_z": abs(z),
            }
        )

    def shutdown(self) -> None:
        self._initialized = False
