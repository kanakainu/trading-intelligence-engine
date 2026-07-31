"""Exit Engine — intelligence-driven exit decisions."""
from dataclasses import dataclass
from typing import Dict, Any
from enum import Enum

from core.features.feature_models import FeatureSnapshot


class ExitDecision(Enum):
    HOLD = "hold"
    PARTIAL = "partial"
    TRAIL = "trail"
    FULL_CLOSE = "full_close"


@dataclass
class ExitEvaluation:
    decision: ExitDecision
    reason: str
    urgency: float          # 0-1
    metadata: Dict[str, Any]


class MomentumDecay:
    """Exit when momentum weakens (body ratio drops)."""
    def evaluate(self, features: FeatureSnapshot, position: Dict) -> ExitEvaluation:
        candles = features.candles.get("M5", [])
        if len(candles) < 3:
            return ExitEvaluation(ExitDecision.HOLD, "insufficient_data", 0.0, {})

        last = candles[-1]
        body = abs(last["close"] - last["open"])
        total = last["high"] - last["low"]
        body_ratio = body / total if total else 0

        if body_ratio < 0.3:  # Weak body
            return ExitEvaluation(ExitDecision.PARTIAL, "momentum_decay", 0.6, {"body_ratio": body_ratio})
        return ExitEvaluation(ExitDecision.HOLD, "momentum_ok", 0.0, {"body_ratio": body_ratio})


class VelocityDrop:
    """Exit when tick speed drops drastically (momentum drying up).

    Uses estimated tick_speed from M1 body ratio — faster than trailing stop.
    """
    def evaluate(self, features: FeatureSnapshot, position: Dict) -> ExitEvaluation:
        candles_m1 = features.candles.get("M1", [])
        if len(candles_m1) < 5:
            return ExitEvaluation(ExitDecision.HOLD, "insufficient_data", 0.0, {})

        # Tick speed = body/range ratio. Recent 3 vs prior 5.
        def _avg_body_ratio(cs):
            ratios = []
            for c in cs:
                rng = float(c["high"]) - float(c["low"])
                ratios.append(abs(float(c["close"]) - float(c["open"])) / rng if rng > 0 else 0)
            return sum(ratios) / len(ratios)

        recent_speed = _avg_body_ratio(candles_m1[-3:])
        prior_speed  = _avg_body_ratio(candles_m1[-8:-3]) if len(candles_m1) >= 8 else recent_speed

        drop_ratio = recent_speed / (prior_speed + 1e-9)
        # tick speed dropped to < 30% of prior avg = velocity stop
        if drop_ratio < 0.3:
            return ExitEvaluation(ExitDecision.FULL_CLOSE, "velocity_stop",
                                  0.90, {"recent_speed": round(recent_speed, 3),
                                         "prior_speed": round(prior_speed, 3),
                                         "drop_ratio": round(drop_ratio, 3)})
        # Moderate slow: trail
        if drop_ratio < 0.5:
            return ExitEvaluation(ExitDecision.TRAIL, "velocity_drop",
                                  0.55, {"drop_ratio": round(drop_ratio, 3)})
        return ExitEvaluation(ExitDecision.HOLD, "velocity_ok", 0.0, {"drop_ratio": round(drop_ratio, 3)})


class LiquidityCollapse:
    """Exit when liquidity collapses (volume drops)."""
    def evaluate(self, features: FeatureSnapshot, position: Dict) -> ExitEvaluation:
        volume_ratio = features.volume_ratio.get("M5", 1.0)
        if volume_ratio < 0.5:
            return ExitEvaluation(ExitDecision.FULL_CLOSE, "liquidity_collapse", 0.9, {"volume_ratio": volume_ratio})
        return ExitEvaluation(ExitDecision.HOLD, "liquidity_ok", 0.0, {"volume_ratio": volume_ratio})


class TimeStop:
    """Exit after 6 min no profit (momentum strategy needs momentum)."""
    MAX_HOLD = 6 * 60  # 360s

    def evaluate(self, features: FeatureSnapshot, position: Dict) -> ExitEvaluation:
        entry_time = position.get("entry_time", 0)
        hold_seconds = features.timestamp.timestamp() - entry_time
        entry = position.get("entry_price", 0)
        current = position.get("current_price", 0)
        direction = position.get("direction", "BUY")
        profit = (current - entry) if direction == "BUY" else (entry - current)

        if hold_seconds > self.MAX_HOLD and profit <= 0:
            return ExitEvaluation(ExitDecision.FULL_CLOSE, "time_stop_no_profit",
                                  0.85, {"hold_seconds": hold_seconds, "profit": profit})
        return ExitEvaluation(ExitDecision.HOLD, "time_ok", 0.0, {"hold_seconds": hold_seconds})


class ATRCompression:
    """Exit when ATR compresses (volatility drops)."""
    def evaluate(self, features: FeatureSnapshot, position: Dict) -> ExitEvaluation:
        atr_pct = features.atr_percent.get("M5", 0.01)
        if atr_pct < 0.004:  # Very low volatility
            return ExitEvaluation(ExitDecision.TRAIL, "atr_compression", 0.4, {"atr_pct": atr_pct * 100})
        return ExitEvaluation(ExitDecision.HOLD, "atr_ok", 0.0, {"atr_pct": atr_pct * 100})


class MicroTrailing:
    """Trail stop when profit > 0.5 ATR."""
    def evaluate(self, features: FeatureSnapshot, position: Dict) -> ExitEvaluation:
        entry = position.get("entry_price", 0)
        current = position.get("current_price", 0)
        direction = position.get("direction", "BUY")
        atr = features.get_atr("M5") or 5.0

        profit = (current - entry) if direction == "BUY" else (entry - current)
        profit_atr = profit / atr if atr else 0

        if profit_atr > 0.5:
            return ExitEvaluation(ExitDecision.TRAIL, "micro_trailing", 0.3, {"profit_atr": profit_atr})
        return ExitEvaluation(ExitDecision.HOLD, "no_trail_yet", 0.0, {"profit_atr": profit_atr})


def evaluate_exit(features: FeatureSnapshot, position: Dict) -> ExitEvaluation:
    """Run all exit evaluators, return highest urgency decision."""
    evaluators = [MomentumDecay(), VelocityDrop(), LiquidityCollapse(), TimeStop(), ATRCompression(), MicroTrailing()]
    evals = [ev.evaluate(features, position) for ev in evaluators]
    highest = max(evals, key=lambda e: e.urgency)
    return highest
