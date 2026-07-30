from typing import Any, Dict
from core.rules.plugins.plugin_interface import RulePluginInterface, RuleResult


class ConfidenceRule(RulePluginInterface):
    def initialize(self, config: Dict[str, Any]) -> None:
        self._min = config.get("min_confidence", 0.65)
        self._enabled = config.get("enabled", True)

    def evaluate(self, context, facts, setup_result=None, decision=None) -> RuleResult:
        confidence = 0.0
        if decision and hasattr(decision, "confidence"):
            confidence = decision.confidence
        elif isinstance(decision, dict):
            confidence = decision.get("confidence", 0.0)
        elif setup_result and hasattr(setup_result, "confidence"):
            confidence = setup_result.confidence

        # Normalise Bystra 0-10 → 0-1
        if confidence > 1.0:
            confidence = confidence / 10.0

        if confidence < self._min:
            return RuleResult("REJECT", f"Confidence {confidence:.0%} < min {self._min:.0%}",
                              metadata={"confidence": confidence}, priority=self.priority())
        return RuleResult("APPROVE", f"Confidence {confidence:.0%} OK", priority=self.priority())

    def metadata(self): return {"name": "confidence_rule", "type": "risk"}
    def priority(self) -> int: return 5
    def enabled(self) -> bool: return getattr(self, "_enabled", True)
