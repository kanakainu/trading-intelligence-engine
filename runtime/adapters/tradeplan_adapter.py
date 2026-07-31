"""TradePlanAdapter — convert TradePlan → TradeDecision for production pipeline.

Phase D2: shadow mode only. Old orchestrator still executes.
New MultiStrategyRuntime runs in parallel, logs differences.
No execution behavior change.
"""
from __future__ import annotations
import logging
from typing import Optional

from core.decision.trade_decision import TradeDecision, BUY, SELL, WAIT
from core.planner.planner_models import TradePlan

log = logging.getLogger("TradePlanAdapter")


def plan_to_decision(plan: Optional[TradePlan]) -> TradeDecision:
    """Convert TradePlan → TradeDecision (same shape EntryMonitor expects)."""
    if plan is None:
        return TradeDecision(action=WAIT, reason="no_plan")

    direction = plan.direction.upper()
    action = BUY if direction == "BUY" else SELL if direction == "SELL" else WAIT
    setup_name = f"MSR_{direction}"

    decision = TradeDecision(
        action=action,
        setup_id=plan.plan_id,
        setup_name=setup_name,
        confidence=plan.risk_reward / 3.0,  # normalize RR→confidence proxy
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

from strategies.aggressive.regime.regime_snapshot import AggressiveRegimeSnapshot, AggressiveRegime
from core.regime.regime_models import RegimeSnapshot, Regime, TrendDirection

def aggressive_regime_to_core_regime(agg_regime: AggressiveRegimeSnapshot) -> RegimeSnapshot:
    """Converts AggressiveRegimeSnapshot to core RegimeSnapshot.

    This is a temporary adaptation for ScanContext which expects core.regime.RegimeSnapshot.
    A proper long-term solution might involve unifying regime models or a more robust adapter.
    """
    # Map AggressiveRegime to core.regime.Regime
    regime_map = {
        AggressiveRegime.TRENDING_BULL: Regime.TRENDING,
        AggressiveRegime.TRENDING_BEAR: Regime.TRENDING,
        AggressiveRegime.WEAK_TREND: Regime.EARLY_TREND, # Best fit for weak trend
        AggressiveRegime.RANGING: Regime.RANGE,
        AggressiveRegime.CHOPPY: Regime.CHOPPY,
        AggressiveRegime.HIGH_VOLATILITY: Regime.NEWS, # High vol often linked to news
        AggressiveRegime.LOW_LIQUIDITY: Regime.LOW_LIQUIDITY,
    }

    core_regime_enum = regime_map.get(agg_regime.regime, Regime.UNKNOWN)

    # Map TrendDirection
    trend_direction_enum = TrendDirection.FLAT
    if agg_regime.regime == AggressiveRegime.TRENDING_BULL:
        trend_direction_enum = TrendDirection.UP
    elif agg_regime.regime == AggressiveRegime.TRENDING_BEAR:
        trend_direction_enum = TrendDirection.DOWN

    return RegimeSnapshot(
        regime=core_regime_enum,
        trend_direction=trend_direction_enum,
        confidence=agg_regime.confidence,
        # Placeholder for other fields if needed, or get from FeatureSnapshot in main loop
        timestamp=agg_regime.timestamp, 
        symbol=agg_regime.symbol if hasattr(agg_regime, 'symbol') else "",
        scan_id=agg_regime.scan_id if hasattr(agg_regime, 'scan_id') else "",
    )