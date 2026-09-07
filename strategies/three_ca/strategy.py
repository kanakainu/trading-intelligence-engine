"""
ThreeCa v1.1 — 3-Candle Compression Breakout Strategy
Pattern: C3 → C2(coil kecil) → C1(thrust besar, close tembus range)
Entry market saat thrust terdeteksi; SL extreme range; TP 2R.
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

TP_R = 2.0  # take profit = 2x risiko (teruji replay: R1.5-2 win 61-72%)


class ThreeCaStrategy(BaseStrategy):
    """3-Candle compression-breakout — standalone entry."""

    def __init__(self):
        meta = StrategyMetadata(
            id="three_ca_v1",
            name="ThreeCa",
            version="1.1.0",
            priority=85,
            author="Sasa",
            description="3-candle coil->breakout thrust: market entry, SL range extreme, TP 2R"
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

        # Same-candle guard: satu sinyal per candle closed terakhir
        m5 = (market_ctx.metadata.get("candles") or {}).get("M5", [])
        if m5:
            lc = m5[-2] if len(m5) >= 2 else m5[-1]
            _ckey = f"{lc.get('time') or lc.get('high',0)}_{lc.get('close',0)}"
            if _ckey == getattr(self, "_last_candle_key", None):
                return StrategyResult(signal=None, confidence=0.0, reason="no_pattern")
        else:
            _ckey = None

        try:
            facts = self._detector.detect(market_ctx)
        except Exception as e:
            logger.warning("[3Ca] detector error: %s", e)
            return StrategyResult(signal=None, confidence=0.0, reason=f"detector_error:{e}")

        if not facts:
            return StrategyResult(signal=None, confidence=0.0, reason="no_pattern")

        best = facts[0]  # terbaru (detector sudah urut baru→lama)
        md = best.metadata
        direction = Direction.BUY if md["direction"] == "BUY" else Direction.SELL
        sl = float(md["sl"])

        # Market-only: thrust C1 baru closed = momentum live. Entry di harga sekarang.
        risk = abs(price - sl)
        if risk <= 0.5:  # SL kelewat dekat = noise, skip (biar R gak ngawur)
            return StrategyResult(signal=None, confidence=0.0, reason="risk_too_small")
        tp = price + TP_R * risk * (1 if direction == Direction.BUY else -1)

        if _ckey:
            self._last_candle_key = _ckey
        logger.info(f"[3Ca] MARKET ENTRY: {direction.name} @ {price:.2f} SL={sl:.2f} TP={tp:.2f} (risk=${risk:.2f})")
        signal = Signal(
            signal_id=str(uuid.uuid4()),
            strategy=self.id,
            symbol=sym,
            direction=direction,
            entry_zone={"price": price, "high": price+0.2, "low": price-0.2},
            confidence=0.85,
            timeframe="M5",
            metadata={
                "sl": sl,
                "take_profit": tp,
                "cutloss": sl,
                "setup_type": "3Ca",
                "strategy_code": "3Ca",
                "volume": 0.05
            }
        )
        return StrategyResult(signal=signal, confidence=0.85, reason="3Ca_breakout_thrust", metadata=signal.metadata)

    def shutdown(self) -> None:
        self._initialized = False
