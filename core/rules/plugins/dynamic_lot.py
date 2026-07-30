"""DynamicLotPlugin — validate lot size against account risk rules."""
from typing import Any, Dict
from core.rules.plugins.plugin_interface import RulePluginInterface, RuleResult


class DynamicLotPlugin(RulePluginInterface):
    def initialize(self, config: Dict[str, Any]) -> None:
        self._min_lot = config.get("min_lot", 0.01)
        self._max_lot = config.get("max_lot", 1.0)
        self._risk_pct = config.get("risk_pct", 0.02)  # 2% default
        self._enabled = config.get("enabled", True)

    def evaluate(self, context: Dict[str, Any], facts: Dict[str, Any],
                 setup_result: Any = None, decision: Any = None) -> RuleResult:
        balance = context.get("balance", 0)
        lot = context.get("lot", 0)
        sl_pips = context.get("sl_pips", 0)

        if lot <= 0:
            return RuleResult("REJECT", "Lot size zero or missing", priority=self.priority())
        if lot < self._min_lot:
            return RuleResult("REJECT", f"Lot {lot} < min {self._min_lot}", priority=self.priority())
        if lot > self._max_lot:
            return RuleResult("REJECT", f"Lot {lot} > max {self._max_lot}", priority=self.priority())

        # Optional risk-based validation
        if balance > 0 and sl_pips > 0:
            risk_usd = lot * sl_pips * 10  # approximate
            risk_ratio = risk_usd / balance
            if risk_ratio > self._risk_pct:
                return RuleResult("REJECT",
                    f"Risk {risk_ratio:.1%} > max {self._risk_pct:.1%}",
                    metadata={"risk_usd": risk_usd, "risk_ratio": risk_ratio},
                    priority=self.priority())

        return RuleResult("APPROVE", "Lot valid", priority=self.priority())

    def metadata(self) -> Dict[str, Any]:
        return {"name": "dynamic_lot", "type": "risk", "version": "1.0"}

    def priority(self) -> int: return 20
    def enabled(self) -> bool: return getattr(self, "_enabled", True)
