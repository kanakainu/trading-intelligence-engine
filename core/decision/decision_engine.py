"""Decision Engine — SetupResult → Decision. No broker. No MT5. Broker-agnostic."""
import logging
import uuid
from typing import List
from core.setup.setup_result import SetupResult, SetupStatus
from core.decision.decision import Decision, Action
from core.decision.execution_plan import ExecutionPlan

log = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.5  # below this → WAIT regardless of setup


class DecisionEngine:
    def decide(self, setup_results: List[SetupResult]) -> List[Decision]:
        decisions = []
        for result in setup_results:
            log.info(f"Loaded SetupResult: {result.setup_id} {result.status}")
            decision = self._evaluate(result)
            log.info(f"Decision Generated | Action: {decision.action} | Confidence: {decision.confidence:.2f}")
            decisions.append(decision)
        return decisions

    def _evaluate(self, result: SetupResult) -> Decision:
        decision_id = str(uuid.uuid4())[:8]

        if result.status == SetupStatus.FAIL or result.confidence < MIN_CONFIDENCE:
            return Decision(
                decision_id=decision_id,
                action=Action.WAIT,
                confidence=result.confidence,
                reason=f"Setup {result.setup_id} FAIL or low confidence ({result.confidence:.2f})",
                setup_id=result.setup_id,
            )

        # Direction comes from setup metadata (knowledge pack defines it — not hardcoded)
        direction = result.metadata.get("direction", "").upper()
        action = Action.BUY if direction == "BUY" else Action.SELL if direction == "SELL" else Action.WAIT

        plan = None
        if action in (Action.BUY, Action.SELL):
            plan = ExecutionPlan(
                entry_type=result.metadata.get("entry_type", "market"),
                entry_zone=float(result.metadata.get("entry_zone", 0.0)),
                stop_loss=float(result.metadata.get("stop_loss", 0.0)),
                take_profit=float(result.metadata.get("take_profit", 0.0)),
                risk_profile=result.metadata.get("risk_profile", "medium"),
                notes=f"Auto-generated from {result.setup_id}",
            )
            log.info("Execution Plan Ready")

        return Decision(
            decision_id=decision_id,
            action=action,
            confidence=result.confidence,
            reason=f"Setup {result.setup_id} PASS conf={result.confidence:.2f}",
            setup_id=result.setup_id,
            execution_plan=plan,
            metadata=result.metadata,
        )
