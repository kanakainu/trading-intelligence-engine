"""
ThreeCa v1.0 — Standalone 3-Candle Compression Strategy
Pattern: C3(big) → C2(small/inside) → C1(big breakout, same dir)
Extracted from Bystra. Runs independently alongside RiriScalps.
"""
import uuid
import logging

from core.strategy.base_strategy import BaseStrategy
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.strategy.strategy_metadata import StrategyMetadata
from core.signals.signal import Signal, Direction

from detectors.three_candle_detector import ThreeCandleDetector

logger = logging.getLogger("ThreeCa")


class ThreeCaStrategy(BaseStrategy):
    """3-Candle Compression — standalone CAPYBARS-style entry."""

    def __init__(self):
        meta = StrategyMetadata(
            id="three_ca_v1",
            name="ThreeCa",
            version="1.0.0",
            priority=85,
            author="Sasa",
            description="3-candle big-small-big compression: entry at C2 zone, SL beyond C3"
        )
        super().__init__(meta)
        self._detector = ThreeCandleDetector()

    def initialize(self) -> None:
        self._initialized = True

    def observe(self, context: StrategyContext) -> None:
        pass

    def analyze(self, context: StrategyContext) -> StrategyResult:
        market_ctx = context.scan.market

        # Spread guard
        spread = getattr(market_ctx, "spread", 0.0) or 0.0
        if spread > 0.5:
            return StrategyResult(signal=None, confidence=0.0, reason=f"spread_trap={spread:.2f}")

        # Run detector
        try:
            facts = self._detector.detect(market_ctx)
        except Exception as e:
            logger.warning("[3Ca] detector error: %s", e)
            return StrategyResult(signal=None, confidence=0.0, reason=f"detector_error:{e}")

        if not facts:
            return StrategyResult(signal=None, confidence=0.0, reason="no_pattern")

        best = max(facts, key=lambda f: f.confidence)
        md = best.metadata or {}
        direction_str = md.get("direction", "")
        if not direction_str:
            return StrategyResult(signal=None, confidence=0.0, reason="no_direction")

        direction = Direction.BUY if direction_str == "BUY" else Direction.SELL

        # Current price fallback
        price = getattr(market_ctx, "current_price", 0.0) or 0.0
        if price == 0.0:
            m5 = getattr(market_ctx, "candles", {}).get("M5", [])
            if m5:
                price = float(m5[-1].get("close", 0.0))

        logger.info(
            "[3Ca] ENTRY: %s conf=%.0f%% sl=%.2f tp=%.2f entry_zone=%s",
            direction_str, best.confidence * 100,
            md.get("sl", 0), md.get("tp", 0), md.get("entry_zone", {})
        )

        signal = Signal(
            signal_id=str(uuid.uuid4()),
            strategy=self.id,
            symbol=market_ctx.symbol,
            direction=direction,
            entry_zone=md.get("entry_zone", {"price": price, "high": price + 0.5, "low": price - 0.5}),
            confidence=best.confidence,
            timeframe=md.get("entry_tf", "M5"),
            metadata=md,
        )

        return StrategyResult(
            signal=signal,
            confidence=best.confidence,
            reason="THREE_CANDLE detected",
            metadata={
                "sl": md.get("sl"),
                "tp": md.get("tp"),
                "danger_zone": md.get("danger_zone"),
                "setup_type": "3Ca",
            }
        )

    def shutdown(self) -> None:
        self._initialized = False
