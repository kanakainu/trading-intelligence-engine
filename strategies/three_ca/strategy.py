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
        sym = market_ctx.symbol
        price = market_ctx.price or (market_ctx.metadata.get("candles", {}).get("M5", [])[-1]["close"] if market_ctx.metadata.get("candles", {}).get("M5", []) else 0)

        # Same-candle guard
        m5 = (market_ctx.metadata.get("candles") or {}).get("M5", [])
        if m5:
            lc = m5[-2] if len(m5) >= 2 else m5[-1]
            _ckey = f"{lc.get('high',0):.2f}_{lc.get('low',0):.2f}_{lc.get('close',0):.2f}"
            if _ckey == getattr(self, "_last_candle_key", None):
                return StrategyResult(signal=None, confidence=0.0, reason="no_pattern")
        else:
            _ckey = None

        # Run detector
        try:
            facts = self._detector.detect(market_ctx)
        except Exception as e:
            logger.warning("[3Ca] detector error: %s", e)
            return StrategyResult(signal=None, confidence=0.0, reason=f"detector_error:{e}")

        if not facts:
            return StrategyResult(signal=None, confidence=0.0, reason="no_pattern")

        best = facts[0] # Take first valid
        md = best.metadata
        direction = Direction.BUY if md["direction"] == "BUY" else Direction.SELL
        c1 = md["c1"]
        c2 = md["c2"]
        
        # Dual-Path Execution Logic (Goodrilla Refined)
        trigger_market = False
        is_limit = False
        entry_level = 0.0
        
        if direction == Direction.BUY:
            if price >= float(c1["high"]):
                trigger_market = True # Immediate breakout
                reason = "3Ca_market_breakout_buy"
            else:
                is_limit = True # Refined entry at C2
                reason = "3Ca_limit_refined_buy"
                entry_level = float(c2["high"])
        else:
            if price <= float(c1["low"]):
                trigger_market = True
                reason = "3Ca_market_breakout_sell"
            else:
                is_limit = True
                reason = "3Ca_limit_refined_sell"
                entry_level = float(c2["low"])

        # Final Decision
        if trigger_market:
            if _ckey: self._last_candle_key = _ckey
            logger.info(f"[3Ca] MARKET ENTRY: {direction.name} at {price:.2f}")
            signal = Signal(
                signal_id=str(uuid.uuid4()),
                strategy=self.id,
                symbol=sym,
                direction=direction,
                entry_zone={"price": price, "high": price+0.2, "low": price-0.2},
                confidence=0.85,
                timeframe="M5",
                metadata={
                    "sl": md["sl"],
                    "take_profit": price + (4.0 if direction==Direction.BUY else -4.0),
                    "cutloss": md["cutloss"],
                    "setup_type": "3Ca",
                    "volume": 0.05
                }
            )
            return StrategyResult(signal=signal, confidence=0.85, reason=reason, metadata=signal.metadata)
            
        elif is_limit:
            # For now, just wait for price to hit c2 high/low
            prox = abs(price - entry_level)
            if prox <= 0.3: # "Limit" hit
                if _ckey: self._last_candle_key = _ckey
                logger.info(f"[3Ca] REFINED LIMIT ENTRY: {direction.name} at {price:.2f} (level={entry_level:.2f})")
                signal = Signal(
                    signal_id=str(uuid.uuid4()),
                    strategy=self.id,
                    symbol=sym,
                    direction=direction,
                    entry_zone={"price": price, "high": price+0.2, "low": price-0.2},
                    confidence=0.82,
                    timeframe="M5",
                    metadata={
                        "sl": md["sl"],
                        "take_profit": price + (4.0 if direction==Direction.BUY else -4.0),
                        "cutloss": md["cutloss"],
                        "setup_type": "3Ca",
                        "volume": 0.05
                    }
                )
                return StrategyResult(signal=signal, confidence=0.82, reason=reason, metadata=signal.metadata)

        return StrategyResult(signal=None, confidence=0.0, reason="waiting_for_trigger")

    def shutdown(self) -> None:
        self._initialized = False
