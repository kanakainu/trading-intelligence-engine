"""
DecisionPipeline — SetupMatch[] → TradeDecision.
No YAML, no candle, no broker, no MT5, no lot, no SL, no TP, no order.
"""
import logging
from typing import Any, Dict, List, Optional
from core.setup.setup_match import SetupMatch, READY
from core.decision.trade_decision import TradeDecision, BUY, SELL, WAIT, SKIP
from core.decision.decision_policy import DecisionPolicy
from core.decision.decision_ranker import rank_candidates
from core.decision.decision_trace import build_trace
from core.decision.decision_explainer import build_explanation

log = logging.getLogger(__name__)


class DecisionPipeline:
    def __init__(self, policy: Optional[DecisionPolicy] = None):
        self._policy = policy or DecisionPolicy()

    def decide(
        self,
        candidates: List[SetupMatch],
        context: Dict[str, Any] = None,
    ) -> TradeDecision:
        ctx = context or {}
        ranked = rank_candidates(candidates, self._policy.setup_priority)
        ranking = [{"id":c.setup_id,"name":c.setup_name,"status":c.status,"conf":c.confidence}
                   for c in ranked]

        # filter READY above min confidence
        eligible = [c for c in ranked
                    if c.status == READY and c.confidence >= self._policy.min_confidence]

        if not eligible:
            low = [c for c in ranked if c.status == READY]
            if low:
                reason = f"No setup meets min confidence ({self._policy.min_confidence:.0%}). Best: {low[0].setup_name} {low[0].confidence:.0%}"
            else:
                reason = "No READY setup found."
            td = TradeDecision(action=WAIT, reason=reason, ranking=ranking,
                               trace=build_trace(ranked, WAIT, reason))
            log.info(f"Decision: WAIT — {reason}")
            return td

        best = eligible[0]
        # Direction from setup metadata or market_bias field
        direction = (best.explanation + " " + best.setup_id).upper()
        if "SELL" in direction or any("sell" in str(m).lower() for m in best.matched_dependencies):
            action = SELL
        else:
            action = BUY  # default: long bias for XAUUSD

        reason = f"Highest confidence: {best.setup_name} {best.confidence:.0%}"
        exp = build_explanation(action, best, reason, ranked)
        trace = build_trace(ranked, action, reason)

        td = TradeDecision(
            action=action,
            setup_id=best.setup_id,
            setup_name=best.setup_name,
            confidence=best.confidence,
            reason=reason,
            ranking=ranking,
            trace=trace,
            explanation=exp,
        )
        log.info(f"Decision: {action} setup={best.setup_id} conf={best.confidence:.0%}")
        return td

    def skip(self, reason: str = "Manual skip.") -> TradeDecision:
        return TradeDecision(action=SKIP, reason=reason)
