"""TradePlanAdapter — convert TradePlan → TradeDecision for production pipeline.

Phase D3: Full production. MultiStrategyRuntime as main decision engine.
"""
from __future__ import annotations
import logging
from typing import Optional
from datetime import datetime, timezone

from core.decision.trade_decision import TradeDecision, BUY, SELL, WAIT
from core.planner.planner_models import TradePlan
from strategies.aggressive.regime.regime_snapshot import AggressiveRegimeSnapshot, AggressiveRegime
from core.regime.regime_models import RegimeSnapshot, Regime, TrendDirection

log = logging.getLogger("TradePlanAdapter")


def plan_to_decision(plan: Optional[TradePlan]) -> TradeDecision:
    """Convert TradePlan → TradeDecision (same shape EntryMonitor expects)."""
    if plan is None:
        return TradeDecision(action=WAIT, reason="no_plan")

    direction = plan.direction.upper()
    action = BUY if direction == "BUY" else SELL if direction == "SELL" else WAIT
    # Use injected strategy code (B, BA, BAS) instead of fixed MSR
    code = (plan.metadata or {}).get("strategy_code", "MSR")
    setup_name = f"{code}_{direction}"

    # Normalize confidence to 0-1 range
    normalized_confidence = min(max(plan.confidence, 0.0), 1.0)
    
    decision = TradeDecision(
        action=action,
        setup_id=plan.plan_id,
        setup_name=setup_name,
        confidence=normalized_confidence,
        reason=f"MSR plan rr={plan.risk_reward:.2f}",
        explanation=f"entry={plan.entry_zone} sl={plan.sl} tp={plan.tp} rr={plan.risk_reward:.2f}",
    )
    decision.metadata = {
        "entry_zone": plan.entry_zone,
        "sl": plan.sl,
        "take_profit": plan.tp,
        "danger_zone": plan.danger_zone,
        "entry_tf": "M5",
        "risk_reward": plan.risk_reward,
        "volume": plan.position_size,
    }
    # pass through strategy extras (nyao_score/nyao_thr for dampener, strategy_code, cutloss...)
    for _k, _v in (plan.metadata or {}).items():
        decision.metadata.setdefault(_k, _v)
    return decision


def log_shadow_diff(sym: str, old: TradeDecision, new: TradeDecision) -> None:
    """Side-by-side comparison log. NO execution difference."""
    if old.action == new.action and abs(old.confidence - new.confidence) < 0.05:
        log.info("[SHADOW OK] %s old=%s new=%s conf_delta=%.2f",
                 sym, old.action, new.action, new.confidence - old.confidence)
        return

    log.warning(
        "[SHADOW DIFF] %s "
        "old=(%s/%s conf=%.2f sl=%s tp=%s) "
        "new=(%s/%s conf=%.2f sl=%s tp=%s)",
        sym,
        old.action, old.setup_name, old.confidence,
        old.metadata.get("sl"), old.metadata.get("take_profit"),
        new.action, new.setup_name, new.confidence,
        new.metadata.get("sl"), new.metadata.get("take_profit"),
    )


def aggressive_regime_to_core_regime(agg_regime: AggressiveRegimeSnapshot) -> RegimeSnapshot:
    """Converts AggressiveRegimeSnapshot to core RegimeSnapshot.

    This is a temporary adaptation for ScanContext which expects core.regime.RegimeSnapshot.
    A proper long-term solution might involve unifying regime models or a more robust adapter.
    """
    # Map AggressiveRegime to core.regime.Regime
    regime_map = {
        AggressiveRegime.BULL:         Regime.TRENDING,
        AggressiveRegime.BEAR:         Regime.TRENDING,
        AggressiveRegime.MINOR_TREND:  Regime.EARLY_TREND,
        AggressiveRegime.FLAT:         Regime.RANGE,
    }

    core_regime_enum = regime_map.get(agg_regime.regime, Regime.UNKNOWN)

    # Map TrendDirection
    trend_direction_enum = TrendDirection.FLAT
    if agg_regime.regime == AggressiveRegime.BULL:
        trend_direction_enum = TrendDirection.UP
    elif agg_regime.regime == AggressiveRegime.BEAR:
        trend_direction_enum = TrendDirection.DOWN

    return RegimeSnapshot(
        regime=core_regime_enum,
        trend_direction=trend_direction_enum,
        confidence=agg_regime.confidence,
        timestamp=agg_regime.timestamp,
    )
