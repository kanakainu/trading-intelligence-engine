"""Decision Validator — checks confidence, action, mandatory fields, plan completeness."""
from typing import Any, Dict, List, Tuple
from core.decision.decision import Decision, Action
from core.decision.execution_plan import ExecutionPlan

MIN_CONFIDENCE = 0.0
MAX_CONFIDENCE = 1.0


class DecisionValidator:
    def validate(self, decision: Decision) -> Tuple[bool, List[str]]:
        errors = []

        if not decision.decision_id:
            errors.append("missing:decision_id")
        if not decision.setup_id:
            errors.append("missing:setup_id")
        if not isinstance(decision.action, Action):
            errors.append(f"invalid_action:{decision.action}")
        if not (MIN_CONFIDENCE <= decision.confidence <= MAX_CONFIDENCE):
            errors.append(f"invalid_confidence:{decision.confidence}")
        if decision.action in (Action.BUY, Action.SELL) and decision.execution_plan is None:
            errors.append("missing:execution_plan")
        if decision.execution_plan and not decision.execution_plan.is_complete():
            errors.append("incomplete:execution_plan")

        return len(errors) == 0, errors
