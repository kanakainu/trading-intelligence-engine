"""AggressiveStrategy — full integration of all Aggressive components."""
from typing import Optional
import logging

from core.strategy.base_strategy import BaseStrategy
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_result import StrategyResult
from core.signals.signal import Signal, Direction
from core.lifecycle.lifecycle_models import PositionSnapshot
from core.learning.learning_models import TradeReflection

from strategies.aggressive.metadata import AGGRESSIVE_METADATA
from strategies.aggressive.regime import AggressiveRegimeEngine
from strategies.aggressive.liquidity.liquidity_engine import evaluate_liquidity
from strategies.aggressive.market_pulse.market_pulse import compute_pulse
from strategies.aggressive.session.session_profile import evaluate_session
from strategies.aggressive.detectors import (
    MomentumBurst, VWAPMagnet, RibbonRide,
    CompressionBreak, VelocitySpike, PullbackQuality, LiquidityVacuum
)
from strategies.aggressive.confidence import compute_confidence
from strategies.aggressive.scoring import score_entry, REJECT
from strategies.aggressive.exits import evaluate_exit, ExitDecision
from strategies.aggressive.opportunity.opportunity_engine import OpportunityWindow
from strategies.aggressive.governor.daily_governor import DailyProfitGovernor
from strategies.aggressive.metrics.metrics_logger import MetricsLogger
from strategies.aggressive.cooldown.cooldown_engine import AdaptiveCooldown

logger = logging.getLogger(__name__)


class AggressiveStrategy(BaseStrategy):
    """Aggressive scalping strategy — full integration."""

    def __init__(self):
        super().__init__(AGGRESSIVE_METADATA)
        self._regime_engine = AggressiveRegimeEngine()
        self._detectors = [
            MomentumBurst(), VWAPMagnet(), RibbonRide(),
            CompressionBreak(), VelocitySpike(), PullbackQuality(), LiquidityVacuum()
        ]
        self._governor = DailyProfitGovernor()
        self._cooldown = AdaptiveCooldown()
        self._metrics = MetricsLogger()
        self._opportunity_engine = OpportunityWindow()

    def initialize(self) -> None:
        self._initialized = True
        logger.info("AggressiveStrategy initialized — C7 Pipeline")

    def observe(self, context: StrategyContext) -> None:
        pass

    def analyze(self, context: StrategyContext) -> StrategyResult:
        """Pipeline: Governor → Cooldown → Session → Liquidity → Pulse → Opportunity → Regime → Detectors → Confidence → Entry Scoring → Signal"""
        features = context.scan.features
        if not features:
            return StrategyResult(signal=None, confidence=0.0, reason="no_features")

        # -2. Governor
        gov_status = self._governor.get_status()
        if gov_status["halted"]:
            return StrategyResult(signal=None, confidence=0.0, reason=f"governor_halted={gov_status['reason']}")

        # -1. Cooldown
        if not self._cooldown.can_trade():
            remaining = int(self._cooldown.remaining())
            return StrategyResult(signal=None, confidence=0.0, reason=f"cooldown={remaining}s")

        # 0. Session gate
        session = evaluate_session(features.timestamp)
        if not session.allowed:
            return StrategyResult(signal=None, confidence=0.0, reason=f"session_reject={session.session}")

        # 1. Liquidity
        candles_m1 = features.candles.get("M1", [])
        spread = features.spread if isinstance(features.spread, float) else 0.0
        atr = features.get_atr("M1") or 0.0
        volume_ratio = features.volume_ratio.get("M1", 1.0)
        liquidity = evaluate_liquidity(features.symbol, spread, atr, candles_m1, volume_ratio)

        # 2. Market Pulse
        candles_m5 = features.candles.get("M5", [])
        pulse = compute_pulse(candles_m5)

        # 3. Opportunity Window
        opportunity = self._opportunity_engine.evaluate(session, liquidity, pulse, spread)
        if opportunity.window == "CLOSED":
            return StrategyResult(signal=None, confidence=0.0, reason=f"opportunity_closed={opportunity.reason}")

        # 4. Regime
        regime = self._regime_engine.classify(features)

        # 5. Detectors
        results = [d.detect(features, regime) for d in self._detectors]
        fired = [r for r in results if r is not None]
        if not fired:
            return StrategyResult(signal=None, confidence=0.0, reason="no_detector_fired")

        # 6. Confidence Engine
        conf = compute_confidence(results, regime, liquidity=liquidity, pulse=pulse, session=session, opportunity=opportunity)
        if conf.verdict == "REJECT":
            return StrategyResult(signal=None, confidence=0.0, reason=f"confidence_reject={conf.confidence}")

        # 7. Entry Scoring
        names = [d.name for d in self._detectors]
        entry = score_entry(results, regime, names)
        if entry.score < REJECT:
            return StrategyResult(signal=None, confidence=0.0, reason=f"score_reject={entry.score}")

        # 8. Build Signal
        signal = Signal(
            signal_id=f"agg_{features.symbol}_{features.timestamp.timestamp()}",
            symbol=features.symbol,
            strategy=self.id,
            direction=Direction.BUY if entry.direction == "BUY" else Direction.SELL,
            timeframe="M5",
            confidence=entry.confidence,
            entry_zone={"low": 0.0, "high": 0.0},
            metadata={
                "regime": regime.regime.value,
                "entry_score": entry.score,
                "entry_label": entry.label,
                "confidence_verdict": conf.verdict,
                "component_scores": entry.component_scores,
                "liquidity": liquidity.state.value,
                "pulse": pulse.pulse,
                "session": session.session,
                "opportunity": opportunity.window,
                "governor": gov_status
            }
        )

        return StrategyResult(
            signal=signal,
            confidence=entry.confidence,
            reason=f"{entry.label} score={entry.score}",
        )

    def manage_position(self, position: PositionSnapshot, context: StrategyContext) -> Optional[StrategyResult]:
        """Exit Intelligence."""
        features = context.scan.features
        if not features: return None

        pos_dict = {
            "entry_price": position.entry_price,
            "current_price": position.current_price,
            "direction": str(position.direction.value if hasattr(position.direction, "value") else position.direction),
            "entry_time": position.opened_at.timestamp() if position.opened_at else 0,
        }
        exit_eval = evaluate_exit(features, pos_dict)

        if exit_eval.decision == ExitDecision.HOLD:
            return None

        return StrategyResult(
            signal=None,
            confidence=exit_eval.urgency,
            reason=f"exit:{exit_eval.reason}",
        )

    def learn(self, reflection: TradeReflection) -> None:
        """Record trade result to Governor, Cooldown, and Metrics."""
        from core.learning.learning_models import TradeOutcome
        won = reflection.outcome == TradeOutcome.WIN
        pnl = reflection.pnl or 0.0
        
        self._governor.record_trade(pnl)
        self._cooldown.record_trade(won)
        self._metrics.record(
            entry_time=reflection.entry_time.timestamp() if reflection.entry_time else 0,
            exit_time=reflection.exit_time.timestamp() if reflection.exit_time else 0,
            pnl=pnl,
            exit_reason=reflection.exit_reason or "unknown",
            symbol=reflection.symbol
        )
        
        logger.info(f"Learn: won={won} pnl={pnl} gov={self._governor.daily_pnl}")

    def shutdown(self) -> None:
        self._initialized = False


    def shutdown(self) -> None:
        self._initialized = False
