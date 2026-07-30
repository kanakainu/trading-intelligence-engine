from typing import Any, Dict
from core.rules.plugins.plugin_interface import RulePluginInterface, RuleResult


class SpreadRule(RulePluginInterface):
    def initialize(self, config: Dict[str, Any]) -> None:
        self._max_spread = config.get("max_spread", 300)
        self._enabled = config.get("enabled", True)

    def evaluate(self, context, facts, setup_result=None, decision=None) -> RuleResult:
        spread = context.get("spread", 0) or facts.get("spread", 0)
        if spread > self._max_spread:
            return RuleResult("REJECT", f"Spread {spread} > max {self._max_spread}",
                              metadata={"spread": spread}, priority=self.priority())
        return RuleResult("APPROVE", f"Spread {spread} OK", priority=self.priority())

    def metadata(self): return {"name": "spread_rule", "type": "risk"}
    def priority(self) -> int: return 15
    def enabled(self) -> bool: return getattr(self, "_enabled", True)
