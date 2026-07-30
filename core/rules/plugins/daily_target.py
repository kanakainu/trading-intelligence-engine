"""DailyTargetPlugin — REJECT if daily target already hit or exceeded."""
from typing import Any, Dict
from core.rules.plugins.plugin_interface import RulePluginInterface, RuleResult


class DailyTargetPlugin(RulePluginInterface):
    def initialize(self, config: Dict[str, Any]) -> None:
        self._target_usd = config.get("target_usd", 30.0)
        self._enabled = config.get("enabled", True)

    def evaluate(self, context: Dict[str, Any], facts: Dict[str, Any],
                 setup_result: Any = None, decision: Any = None) -> RuleResult:
        daily_pnl = context.get("daily_pnl", 0)

        if daily_pnl >= self._target_usd:
            return RuleResult("REJECT",
                f"Daily target ${self._target_usd} reached (PnL=${daily_pnl:.2f})",
                metadata={"daily_pnl": daily_pnl, "target": self._target_usd},
                priority=self.priority())

        return RuleResult("APPROVE",
            f"Daily PnL ${daily_pnl:.2f} / target ${self._target_usd}",
            priority=self.priority())

    def metadata(self) -> Dict[str, Any]:
        return {"name": "daily_target", "type": "risk", "version": "1.0"}

    def priority(self) -> int: return 40
    def enabled(self) -> bool: return getattr(self, "_enabled", True)
