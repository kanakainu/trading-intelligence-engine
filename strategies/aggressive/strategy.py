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

    def initialize(self) -> None:
        self._initialized = True
        logger.info("AggressiveStrategy initialized — 7 detectors")

    def observe(self, context: StrategyContext) -> None:
        pass

    def analyze(self, context: StrategyContext) -> StrategyResult:
        """Pipeline: Session → Liquidity → Pulse → Regime → Detectors → Confidence → Entry Scoring → Signal"""
        features = context.scan.features
        if not features:
            return StrategyResult(signal=None, confidence=0.0, reason="no_features")

        # 0. Session gate
        session = evaluate_session(features.timestamp)
        if not session.allowed:
            logger.debug(f"Session REJECT: {session.session} score={session.score}")
            return StrategyResult(signal=None, confidence=0.0, reason=f"session_reject={session.session}")

        # 1. Liquidity
        candles_m1 = features.candles.get("M1", [])
        spread = features.spread if isinstance(features.spread, float) else 0.0
        atr = features.get_atr("M1") or 0.0
        volume_ratio = features.volume_ratio.get("M1", 1.0)
        liquidity = evaluate_liquidity(features.symbol, spread, atr, candles_m1, volume_ratio)
        logger.debug(f"Liquidity: {liquidity.state.value} score={liquidity.score}")

        # 2. Market Pulse
        candles_m5 = features.candles.get("M5", [])
        pulse = compute_pulse(candles_m5)
        logger.debug(f"Pulse: {pulse.pulse} {pulse.verdict}")

        # 3. Regime
        regime = self._regime_engine.classify(features)
        logger.debug(f"Regime: {regime.regime.value} conf={regime.confidence:.2f}")

        # 4. Detectors
        results = [d.detect(features, regime) for d in self._detectors]
        fired = [r for r in results if r is not None]
        if not fired:
            return StrategyResult(signal=None, confidence=0.0, reason="no_detector_fired")

        # 5. Confidence Engine (meta-validation with new inputs)
        conf = compute_confidence(results, regime, liquidity=liquidity, pulse=pulse, session=session)
        logger.debug(f"Confidence: {conf.confidence} {conf.verdict}")
        if conf.verdict == "REJECT":
            return StrategyResult(signal=None, confidence=0.0, reason=f"confidence_reject={conf.confidence}")

        # 4. Entry Scoring
        names = [d.name for d in self._detectors]
        entry = score_entry(results, regime, names)
        logger.debug(f"Entry Score: {entry.score} {entry.label} {entry.direction}")
        if entry.score < REJECT:
            return StrategyResult(signal=None, confidence=0.0, reason=f"score_reject={entry.score}")

        # 5. Build Signal
        signal = Signal(
            signal_id=f"agg_{features.symbol}_{features.timestamp.timestamp()}",
            symbol=features.symbol,
            strategy=self.id,
            direction=Direction.BUY if entry.direction == "BUY" else Direction.SELL,
            timeframe="M5",
            confidence=entry.confidence,
            entry_zone={"low": 0.0, "high": 0.0},  # TradePlanner fills later
            metadata={
                "regime": regime.regime.value,
                "entry_score": entry.score,
                "entry_label": entry.label,
                "confidence_verdict": conf.verdict,
                "component_scores": entry.component_scores,
                "liquidity": liquidity.state.value,
                "liquidity_score": liquidity.score,
                "pulse": pulse.pulse,
                "pulse_verdict": pulse.verdict,
                "session": session.session,
                "session_score": session.score,
            }
        )

        return StrategyResult(
            signal=signal,
            confidence=entry.confidence,
            reason=f"{entry.label} score={entry.score}",
        )

    def manage_position(self, position: PositionSnapshot, context: StrategyContext) -> Optional[StrategyResult]:
        """Exit Intelligence — evaluate position and return exit signal if needed."""
        features = context.scan.features
        if not features:
            return None

        pos_dict = {
            "entry_price": position.entry_price,
            "current_price": position.current_price,
            "direction": str(position.direction.value if hasattr(position.direction, "value") else position.direction),
            "entry_time": position.opened_at.timestamp() if position.opened_at else 0,
        }
        exit_eval = evaluate_exit(features, pos_dict)
        logger.debug(f"Exit: {exit_eval.decision.value} urgency={exit_eval.urgency:.2f} reason={exit_eval.reason}")

        if exit_eval.decision == ExitDecision.HOLD:
            return None

        # Exit signal — return metadata only, no Direction.CLOSE
        return StrategyResult(
            signal=None,  # Exit handled by lifecycle/planner, not signal
            confidence=exit_eval.urgency,
            reason=f"exit:{exit_eval.reason}",
        )

    def learn(self, reflection: TradeReflection) -> None:
        pass

    def shutdown(self) -> None:
        self._initialized = False
