from typing import Any, Dict
from core.rules.plugins.plugin_interface import RulePluginInterface, RuleResult


class SLValidationRule(RulePluginInterface):
    """SL must be on the correct side of entry for BUY/SELL."""
    def initialize(self, config: Dict[str, Any]) -> None:
        self._enabled = config.get("enabled", True)

    def evaluate(self, context, facts, setup_result=None, decision=None) -> RuleResult:
        entry = context.get("entry")
        sl = context.get("sl")
        direction = context.get("direction", "BUY").upper()

        if entry is None or sl is None:
            return RuleResult("APPROVE", "No entry/sl — skip", priority=self.priority())

        if direction == "BUY" and sl >= entry:
            return RuleResult("REJECT", f"BUY: SL {sl} must be < entry {entry}",
                              priority=self.priority())
        if direction == "SELL" and sl <= entry:
            return RuleResult("REJECT", f"SELL: SL {sl} must be > entry {entry}",
                              priority=self.priority())
        return RuleResult("APPROVE", f"SL {sl} valid for {direction}", priority=self.priority())

    def metadata(self): return {"name": "sl_validation_rule", "type": "risk"}
    def priority(self) -> int: return 35
    def enabled(self) -> bool: return getattr(self, "_enabled", True)


class TPValidationRule(RulePluginInterface):
    """TP must be on the correct side of entry for BUY/SELL."""
    def initialize(self, config: Dict[str, Any]) -> None:
        self._enabled = config.get("enabled", True)

    def evaluate(self, context, facts, setup_result=None, decision=None) -> RuleResult:
        entry = context.get("entry")
        tp = context.get("tp")
        direction = context.get("direction", "BUY").upper()

        if entry is None or tp is None:
            return RuleResult("APPROVE", "No entry/tp — skip", priority=self.priority())

        if direction == "BUY" and tp <= entry:
            return RuleResult("REJECT", f"BUY: TP {tp} must be > entry {entry}",
                              priority=self.priority())
        if direction == "SELL" and tp >= entry:
            return RuleResult("REJECT", f"SELL: TP {tp} must be < entry {entry}",
                              priority=self.priority())
        return RuleResult("APPROVE", f"TP {tp} valid for {direction}", priority=self.priority())

    def metadata(self): return {"name": "tp_validation_rule", "type": "risk"}
    def priority(self) -> int: return 36
    def enabled(self) -> bool: return getattr(self, "_enabled", True)
