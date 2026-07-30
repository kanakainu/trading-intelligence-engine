"""AdaptiveDrawdownPlugin — REJECT if drawdown exceeds limit."""
from typing import Any, Dict
from core.rules.plugins.plugin_interface import RulePluginInterface, RuleResult


class AdaptiveDrawdownPlugin(RulePluginInterface):
    def initialize(self, config: Dict[str, Any]) -> None:
        self._limit_pct = config.get("limit_pct", 0.05)
        self._enabled = config.get("enabled", True)

    def evaluate(self, context: Dict[str, Any], facts: Dict[str, Any],
                 setup_result: Any = None, decision: Any = None) -> RuleResult:
        equity = context.get("equity", 0)
        peak = context.get("peak_balance", 0)

        if peak <= 0:
            return RuleResult("APPROVE", "No peak balance", priority=self.priority())

        dd = (peak - equity) / peak
        if dd > self._limit_pct:
            return RuleResult("REJECT",
                f"Drawdown {dd:.1%} > limit {self._limit_pct:.1%}",
                metadata={"drawdown": dd, "equity": equity, "peak": peak},
                priority=self.priority())

        return RuleResult("APPROVE", f"Drawdown {dd:.1%} OK", priority=self.priority())

    def metadata(self) -> Dict[str, Any]:
        return {"name": "adaptive_drawdown", "type": "risk", "version": "1.0"}

    def priority(self) -> int: return 30
    def enabled(self) -> bool: return getattr(self, "_enabled", True)
