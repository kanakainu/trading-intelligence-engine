"""
SemiHFT (The Mean Reversion)
Fokus: Z-Score Extremes. Copet profit dari harga jenuh balik ke VWAP.
"""
from typing import Any, Dict, List, Optional
import logging
import uuid

from core.strategy.base_strategy import BaseStrategy
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.strategy.strategy_metadata import StrategyMetadata
from core.signals.signal import Signal, Direction

logger = logging.getLogger("SemiHFTStrategy")

class SemiHFTStrategy(BaseStrategy):
    def __init__(self):
        meta = StrategyMetadata(
            id="semi_hft_c8_v4",
            name="SemiHFT Mean Reversion",
            version="2.0.0",
            priority=90,
            author="Sasa",
            description="Mean Reversion scalp using VWAP Z-Score extremes."
        )
        super().__init__(meta)

    def initialize(self) -> None:
        self._initialized = True

    def observe(self, context: StrategyContext) -> None:
        pass

    def analyze(self, context: StrategyContext) -> StrategyResult:
        market_ctx = context.scan.market
        z_score = market_ctx.vwap_z_score
        price = market_ctx.price

        signal_dir = None
        reason = "z_score_neutral"

        # Mean Reversion Logic (Extreme deviations) — threshold lowered from 2.0 to 1.0
        if z_score < -1.0:
            signal_dir = Direction.BUY
            reason = f"oversold_reversion_z={z_score:.2f}"
        elif z_score > 1.0:
            signal_dir = Direction.SELL
            reason = f"overbought_reversion_z={z_score:.2f}"

        if not signal_dir:
            return StrategyResult(signal=None, confidence=0.0, reason=reason)

        signal = Signal(
            signal_id=str(uuid.uuid4()),
            strategy=self.id,
            symbol="XAUUSD",
            direction=signal_dir,
            entry_zone={"price": price, "high": price + 0.5, "low": price - 0.5},
            confidence=0.75,
            timeframe="M1"
        )

        return StrategyResult(
            signal=signal,
            confidence=0.75,
            reason=reason,
            metadata={"z_score": z_score}
        )

    def shutdown(self) -> None:
        self._initialized = False
