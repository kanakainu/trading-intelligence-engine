"""RiriMicroScalpEngine (RME) — engine-centric, score-based. No detector chains."""
import logging
import uuid
from datetime import datetime
from typing import Optional

from core.strategy.base_strategy import BaseStrategy
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.signals.signal import Signal, Direction
from core.lifecycle.lifecycle_models import PositionSnapshot
from core.learning.learning_models import TradeReflection, TradeOutcome

from strategies.aggressive.metadata import AGGRESSIVE_METADATA
from strategies.aggressive.governor.daily_governor import DailyProfitGovernor
from strategies.aggressive.exits import evaluate_exit, ExitDecision
from strategies.aggressive.metrics.metrics_logger import MetricsLogger
from strategies.aggressive.cooldown.cooldown_engine import AdaptiveCooldown

# RME Score Engines (R1-R3)
from strategies.aggressive.market_snapshot import snapshot as get_snapshot
from strategies.aggressive.opportunity_window import get_session_score
from strategies.aggressive.momentum_engine import calculate_score as calc_momentum_score
from strategies.aggressive.velocity_engine import calculate_score as calc_velocity_score
from strategies.aggressive.microstructure_engine import calculate_score as calc_micro_score
from strategies.aggressive.liquidity_engine import calculate_score as calc_liquidity_score
from strategies.aggressive.vwap_context_engine import calculate_score as calc_vwap_score
from strategies.aggressive.entry_score_engine import calculate as entry_score, EntryScore

logger = logging.getLogger(__name__)


class RiriMicroScalpEngine(BaseStrategy):
    """RME — Riri MicroScalp Engine. Score-based, no gate stacking."""

    def __init__(self):
        super().__init__(AGGRESSIVE_METADATA)
        self._governor = DailyProfitGovernor()
        self._cooldown = AdaptiveCooldown()
        self._metrics = MetricsLogger()

    def initialize(self) -> None:
        self._initialized = True
        logger.info("RiriMicroScalpEngine (RME) initialized — score-based pipeline")

    def observe(self, context: StrategyContext) -> None:
        pass

    def analyze(self, context: StrategyContext) -> StrategyResult:
        features = context.scan.features
        if not features:
            return StrategyResult(signal=None, confidence=0.0, reason="no_features")

        # 1. Governor (only hard gate)
        gov = self._governor.get_status()
        if gov["halted"]:
            return StrategyResult(signal=None, confidence=0.0, reason=f"gov:{gov['reason']}")

        # 2. Cooldown (soft guard)
        if not self._cooldown.can_trade():
            return StrategyResult(signal=None, confidence=0.0, reason=f"cooldown:{int(self._cooldown.remaining())}s")

        # 3. Data prep
        candles_m5 = features.candles.get("M5", [])
        candles_m1 = features.candles.get("M1", [])
        spread    = features.spread if isinstance(features.spread, float) else 0.0
        atr       = features.get_atr("M5") or 0.0
        vol_ratio = features.volume_ratio.get("M5", 1.0)
        price     = getattr(features, "current_price", None) or 0.0
        vwap      = features.vwap.get("M5") if hasattr(features.vwap, "get") else None
        utc_h     = getattr(features.timestamp, "hour", datetime.utcnow().hour)

        # 4. Score all engines (parallel, no gates)
        snap    = get_snapshot(candles_m5)
        sess    = get_session_score(utc_h)
        mom     = calc_momentum_score(candles_m5)
        vel     = calc_velocity_score(candles_m5, atr)
        micro   = calc_micro_score(candles_m5, atr)
        liq     = calc_liquidity_score(vol_ratio)
        vwap_sc = calc_vwap_score(price, vwap)
        trend   = (sess * 0.5 + snap.momentum_score * 0.5)  # composite trend score

        # 5. Determine direction from snapshot
        direction = snap.state  # "BULL"→BUY, "BEAR"→SELL, "FLAT"→NONE
        if direction == "BULL":   direction = "BUY"
        elif direction == "BEAR": direction = "SELL"
        else:                     direction = "NONE"

        # 6. EntryScore aggregator
        es = entry_score(
            momentum_score=mom,
            velocity_score=vel,
            micro_score=micro,
            liquidity_score=liq,
            vwap_score=vwap_sc,
            trend_score=trend,
        )

        if not es.entry_ok:
            return StrategyResult(signal=None, confidence=0.0, reason=f"rme:{es.reason}",
                                  metadata={"score": es.score, "momentum": mom, "velocity": vel,
                                            "micro": micro, "liquidity": liq, "vwap": vwap_sc, "trend": trend})

        # 7. Signal
        sig = Signal(
            signal_id=str(uuid.uuid4())[:8],
            strategy=self.id,
            symbol=features.symbol,
            direction=Direction.BUY if direction == "BUY" else Direction.SELL,
            timeframe="M5",
            confidence=es.score,
            entry_zone={"low": 0.0, "high": 0.0},
            quality_score=es.score,
            metadata={
                "score": es.score, "momentum": mom, "velocity": vel,
                "micro": micro, "liquidity": liq, "vwap": vwap_sc,
                "trend": trend, "session": sess, "state": snap.state,
            }
        )
        logger.info(f"RME {direction} score={es.score:.1f} sym={features.symbol}")
        return StrategyResult(
            signal=sig,
            confidence=es.score,
            reason=f"rme_score:{es.score:.1f}",
            metadata={
                "score": es.score,
                "momentum": mom,
                "velocity": vel,
                "micro": micro,
                "liquidity": liq,
                "vwap": vwap_sc,
                "trend": trend,
            }
        )

    def manage_position(self, position: PositionSnapshot, context: StrategyContext) -> Optional[StrategyResult]:
        features = context.scan.features
        if not features: return None
        pos_dict = {
            "entry_price":   position.entry_price,
            "current_price": position.current_price,
            "direction":     str(position.direction.value if hasattr(position.direction, "value") else position.direction),
            "entry_time":    position.opened_at.timestamp() if position.opened_at else 0,
        }
        exit_eval = evaluate_exit(features, pos_dict)
        if exit_eval.decision == ExitDecision.HOLD: return None
        return StrategyResult(signal=None, confidence=exit_eval.urgency, reason=f"exit:{exit_eval.reason}")

    def learn(self, reflection: TradeReflection) -> None:
        won = reflection.outcome == TradeOutcome.WIN
        pnl = getattr(reflection, "realized_pl", 0.0) or 0.0
        self._governor.record_trade(pnl)
        self._cooldown.record_trade(won)
        self._metrics.record(
            entry_time=reflection.entry_time.timestamp() if reflection.entry_time else 0,
            exit_time=reflection.exit_time.timestamp() if reflection.exit_time else 0,
            pnl=pnl,
            exit_reason=str(reflection.exit_reason.value if hasattr(reflection.exit_reason, "value") else reflection.exit_reason),
            symbol=reflection.symbol
        )

    def shutdown(self) -> None:
        self._initialized = False


# Backward compat alias
AggressiveStrategy = RiriMicroScalpEngine
