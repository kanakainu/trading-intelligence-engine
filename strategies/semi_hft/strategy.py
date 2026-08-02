"""SemiHFT Strategy — pure price action, C8 pipeline."""
import logging
from core.strategy.base_strategy import BaseStrategy
from core.strategy.strategy_metadata import StrategyMetadata
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.learning.learning_models import TradeReflection, TradeOutcome

from .market_state import classify as classify_state, MarketState
from .opportunity import evaluate as eval_opp, OpportunityWindow
from .microstructure import detect as detect_micro, MicroSignal
from .entry_validator import validate as validate_entry
from .attack_engine import plan as attack_plan
from .governor import DailyGovernor
from .learning import LearningLogger

logger = logging.getLogger(__name__)

METADATA = StrategyMetadata(
    id="semi_hft_c8",
    name="SemiHFT",
    version="1.0",
    author="Riri",
    description="C8 Semi-HFT Micro Scalping — pure price action, XAUUSD only",
    supported_symbols=["XAUUSD", "BTCUSD"],
    supported_timeframes=["M1", "M5"],
)


class SemiHFTStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(METADATA)
        self._gov = DailyGovernor()
        self._log = LearningLogger()
        logger.info("SemiHFTStrategy initialized — C8 Pipeline")

    def initialize(self):
        self._initialized = True

    def observe(self, context: StrategyContext) -> None:
        pass

    def analyze(self, context: StrategyContext) -> StrategyResult:
        features = context.scan.features
        if not features:
            return StrategyResult(signal=None, confidence=0.0, reason="no_features")

        # 1. Governor
        if self._gov.is_halted():
            st = self._gov.get_status()
            return StrategyResult(signal=None, confidence=0.0, reason=f"governor:{st['reason']}")

        candles_m1 = features.candles.get("M1", [])
        candles_m5 = features.candles.get("M5", [])
        spread     = float(features.spread) if isinstance(features.spread, (int, float)) else 0.0
        atr_m5     = (features.get_atr("M5") or 0.0)

        import datetime
        utc_hour = features.timestamp.hour if features.timestamp else datetime.datetime.utcnow().hour

        # 2. Market state — relaxed for crypto (no SLEEPING/EXHAUSTED block)
        state_snap = classify_state(candles_m1, candles_m5)
        # ponytail: add volume/volatility check if need stricter filter
        # if state_snap.state in {MarketState.SLEEPING, MarketState.EXHAUSTED}:
        #     return StrategyResult(signal=None, confidence=0.0, reason=f"state:{state_snap.state.value}")

        # 3. Opportunity
        opp = eval_opp(symbol=features.symbol, spread=spread, atr_m5=atr_m5, utc_hour=utc_hour, candles_m1=candles_m1)
        if opp.window != OpportunityWindow.OPEN:
            return StrategyResult(signal=None, confidence=0.0, reason=f"opp_closed:{opp.reason}")

        # 4. Microstructure
        micro = detect_micro(candles_m1)
        if micro.signal == MicroSignal.NONE:
            return StrategyResult(signal=None, confidence=0.0, reason="no_micro_signal")

        # 5. Entry validate
        entry = validate_entry(state_snap, opp, micro)
        if not entry.valid:
            return StrategyResult(signal=None, confidence=0.0, reason=f"invalid:{entry.reason}")

        # 6. Attack plan
        price = features.current_price or 0.0
        equity = getattr(features, "equity", 500.0) or 500.0
        ap = attack_plan(micro.signal, price, candles_m1, equity, micro.pattern)

        # 7. Build signal
        import uuid
        from core.signals.signal import Signal, Direction
        direction = Direction.BUY if micro.signal == MicroSignal.BUY else Direction.SELL
        sig = Signal(
            signal_id=str(uuid.uuid4())[:8],
            strategy="SemiHFT",
            symbol=features.symbol,
            direction=direction,
            entry_zone={"low": price - 0.5, "high": price + 0.5},
            confidence=micro.quality,
            timeframe="M1",
            entry_price_hint=price,
            quality_score=micro.quality,
            metadata={
                "state": state_snap.state.value,
                "opp_score": opp.score,
                "micro_quality": micro.quality,
                "pattern": micro.pattern,
                "sl": ap.sl, "tp": ap.tp, "lot": ap.lot,
                "comment": ap.comment, "rr": ap.rr,
            }
        )
        logger.info(f"C8 signal: {sig.direction} entry={price} sl={ap.sl} tp={ap.tp} lot={ap.lot} pattern={micro.pattern}")
        return StrategyResult(signal=sig, confidence=micro.quality, reason=f"c8_{micro.pattern}")

    def learn(self, reflection: TradeReflection) -> None:
        pnl = getattr(reflection, "realized_pnl", 0.0) or 0.0
        self._gov.record_trade(pnl)
        self._log.record(
            pnl=pnl,
            hold_seconds=getattr(reflection, "hold_seconds", 0),
            exit_reason=getattr(reflection, "exit_reason", ""),
            pattern=getattr(reflection, "pattern", ""),
        )

    def shutdown(self):
        self._initialized = False


if __name__ == "__main__":
    s = SemiHFTStrategy()
    print("C8 OK")
