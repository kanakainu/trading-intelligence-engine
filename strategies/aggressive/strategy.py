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
        """
        Pipeline: Regime → Detectors → Confidence Engine → Entry Scoring → Signal
        """
        features = context.scan.features
        if not features:
            return StrategyResult(signal=None, confidence=0.0, reason="no_features")

        # 1. Regime
        regime = self._regime_engine.classify(features)
        logger.debug(f"Regime: {regime.regime.value} conf={regime.confidence:.2f}")

        # 2. Detectors
        results = [d.detect(features, regime) for d in self._detectors]
        fired = [r for r in results if r is not None]
        if not fired:
            return StrategyResult(signal=None, confidence=0.0, reason="no_detector_fired")

        # 3. Confidence Engine (meta-validation)
        conf = compute_confidence(results, regime)
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
