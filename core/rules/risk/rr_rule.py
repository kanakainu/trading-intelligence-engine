from typing import Any, Dict, Optional
from core.rules.plugins.plugin_interface import RulePluginInterface, RuleResult


class RRRule(RulePluginInterface):
    def initialize(self, config: Dict[str, Any]) -> None:
        self._min_rr = config.get("min_rr", 1.5)
        self._enabled = config.get("enabled", True)

    def evaluate(self, context, facts, setup_result=None, decision=None) -> RuleResult:
        entry = context.get("entry")
        sl = context.get("sl")
        tp = context.get("tp")
        direction = context.get("direction", "BUY").upper()

        if not all([entry, sl, tp]):
            return RuleResult("APPROVE", "No entry/sl/tp — skip RR check", priority=self.priority())

        risk = abs(entry - sl)
        reward = abs(tp - entry)
        if risk == 0:
            return RuleResult("REJECT", "SL = entry (zero risk)", priority=self.priority())

        rr = reward / risk
        # Float tolerance: 1.50 should pass 1.5 min
        if rr < self._min_rr - 0.005:
            return RuleResult("REJECT", f"RR {rr:.2f} < min {self._min_rr}",
                              metadata={"rr": rr, "risk": risk, "reward": reward},
                              priority=self.priority())
        return RuleResult("APPROVE", f"RR {rr:.2f} OK", priority=self.priority())

    def metadata(self): return {"name": "rr_rule", "type": "risk"}
    def priority(self) -> int: return 25
    def enabled(self) -> bool: return getattr(self, "_enabled", True)
