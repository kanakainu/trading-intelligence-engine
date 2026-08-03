"""SemiHFT Strategy V4 — score-based pipeline, no gate stacking."""
import logging
import uuid
from datetime import datetime

from core.strategy.base_strategy import BaseStrategy
from core.strategy.strategy_metadata import StrategyMetadata
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.learning.learning_models import TradeReflection, TradeOutcome
from core.signals.signal import Signal, Direction

from .market_snapshot import snapshot as market_snapshot, MarketSnapshot
from .volatility_engine import calculate_score as vol_score
from .liquidity_map import calculate_score as liq_score
from .opportunity_window import get_session_score
from .market_pulse_engine import calculate_score as pulse_score
from .tick_velocity_engine import calculate_score as tick_vel_score
from .micro_momentum_engine import calculate_score as micro_score, MicroSignal
from .entry_score import calculate as entry_score
from .fast_risk import plan as fast_risk
from .position_heat import calculate as pos_heat, HeatSnapshot
from .exit_intelligence import evaluate as exit_intel
from .daily_governor import DailyGovernor
from .learning import LearningLogger

logger = logging.getLogger(__name__)

METADATA = StrategyMetadata(
    id="semi_hft_c8_v4",
    name="SemiHFT V4",
    version="4.0",
    author="Riri & Sasa",
    description="V4 — Score-based micro scalping, XAUUSD. No gate stacking.",
    supported_symbols=["XAUUSD"],
    supported_timeframes=["M1"],
)

class SemiHFTStrategyV4(BaseStrategy):
    def __init__(self):
        super().__init__(METADATA)
        self._gov = DailyGovernor()
        self._log = LearningLogger()
        # Observe-time state
        self._snap: MarketSnapshot | None = None
        self._vol = self._liq = self._sess = self._pulse = self._vel = 0.0
        self._micro = None  # MicroMomentumSnapshot
        logger.info("SemiHFTStrategyV4 init — C8 Score Pipeline")

    def initialize(self): self._initialized = True

    def observe(self, context: StrategyContext) -> None:
        f = context.scan.features
        if not f: return
        m1 = f.candles.get("M1", [])
        utc_h = getattr(f.timestamp, "hour", datetime.utcnow().hour)
        self._snap  = market_snapshot(m1)
        self._vol   = vol_score(symbol=f.symbol, atr_m5=getattr(f, "atr_m5", 0.0) or 0.0)
        self._liq   = liq_score(symbol=f.symbol, spread=getattr(f, "spread", 0.0) or 0.0, candles_m1=m1)
        self._sess  = get_session_score(utc_h)
        self._pulse = pulse_score(m1)
        self._vel   = tick_vel_score(m1)
        self._micro = micro_score(m1)

    def analyze(self, context: StrategyContext) -> StrategyResult:
        if not self._initialized or self._snap is None:
            return StrategyResult(signal=None, confidence=0.0, reason="init_pending")

        # 1. Governor (only hard gate)
        if self._gov.is_halted():
            return StrategyResult(signal=None, confidence=0.0,
                                  reason=f"gov:{self._gov.get_status()['reason']}")

        # 2. Micro direction + entry score
        micro = self._micro
        if micro is None or micro.signal == MicroSignal.NONE:
            return StrategyResult(signal=None, confidence=0.0, reason="no_micro")

        direction = micro.signal.value  # "BUY" | "SELL"
        es = entry_score(
            momentum_score   = self._snap.momentum_score,
            velocity_score   = self._vel,
            liquidity_score  = self._liq,
            volatility_score = self._vol,
            pulse_score      = self._pulse,
            micro_score      = micro.score,
            direction        = direction,
            pattern          = micro.pattern,
        )
        if not es.entry_ok:
            return StrategyResult(signal=None, confidence=0.0,
                                  reason=f"entry_low:{es.score:.0f}")

        # 3. Risk plan (sole hard-reject: entry/equity == 0)
        f = context.scan.features
        price  = getattr(f, "current_price", None) or getattr(f, "bid", 0.0) or 0.0
        equity = getattr(f, "equity", 500.0) or 500.0
        rp = fast_risk(direction=direction, entry=price,
                       candles_m1=f.candles.get("M1", []),
                       equity=equity, pattern=micro.pattern)
        if not rp.valid:
            return StrategyResult(signal=None, confidence=0.0,
                                  reason=f"risk:{rp.reason}")

        # 4. Position heat (soft check)
        pos = [context.position] if context.position else []
        heat = pos_heat(positions=pos, equity=equity)
        if heat.heat_score > 90:
            return StrategyResult(signal=None, confidence=0.0,
                                  reason=f"heat:{heat.heat_score:.0f}")

        # 5. Signal
        conf = min(100.0, es.score)
        sig = Signal(
            signal_id       = str(uuid.uuid4())[:8],
            strategy        = self.metadata.id,
            symbol          = f.symbol,
            direction       = Direction.BUY if direction == "BUY" else Direction.SELL,
            entry_zone      = {"low": rp.sl, "high": rp.tp},
            confidence      = conf,
            timeframe       = "M1",
            entry_price_hint= price,
            quality_score   = es.score,
            metadata        = {
                "lot": rp.lot, "sl": rp.sl, "tp": rp.tp, "rr": rp.rr,
                "pattern": micro.pattern, "entry_score": es.score,
                "vol": self._vol, "liq": self._liq, "pulse": self._pulse,
                "vel": self._vel, "micro": micro.score,
            }
        )
        logger.info(f"C8V4 {direction} entry={price} sl={rp.sl} tp={rp.tp} "
                    f"lot={rp.lot} pattern={micro.pattern} score={es.score:.1f}")
        return StrategyResult(signal=sig, confidence=conf,
                              reason=f"c8v4_{micro.pattern}")

    def learn(self, reflection: TradeReflection) -> None:
        pnl = getattr(reflection, "realized_pl", 0.0) or 0.0
        self._gov.record_trade(pnl)
        self._log.record(
            symbol          = getattr(reflection, "symbol", "XAUUSD"),
            market_state    = self._snap.state.value if self._snap else "",
            opportunity_score=self._sess,
            entry_reason    = "",
            exit_reason     = str(reflection.exit_reason.value),
            hold_seconds    = getattr(reflection, "duration_seconds", 0.0) or 0.0,
            pnl             = pnl,
            pattern         = getattr(reflection, "entry_regime", ""),
        )

    def shutdown(self): self._initialized = False
