"""DynamicLotPlugin — tiered fixed lot by equity/balance."""
from typing import Any, Dict
from core.rules.plugins.plugin_interface import RulePluginInterface, RuleResult

# ponytail: tiers hardcoded; add config support when user needs runtime override
EQUITY_TIERS = [
    (100,   2000,  0.01),  # fixed 0.01 for small accounts (safe)
    (2001,  5000,  0.02),
    (5001,  10000, 0.05),
]

def _max_lot_for_equity(equity: float) -> float:
    for lo, hi, lot in EQUITY_TIERS:
        if lo <= equity <= hi:
            return lot
    if equity > 10000:
        return 1.00
    return 0.01  # below $100 — minimum


class DynamicLotPlugin(RulePluginInterface):
    def initialize(self, config: Dict[str, Any]) -> None:
        self._min_lot = config.get("min_lot", 0.01)
        self._enabled = config.get("enabled", True)

    def evaluate(self, context: Dict[str, Any], facts: Dict[str, Any],
                 setup_result: Any = None, decision: Any = None) -> RuleResult:
        equity = context.get("equity") or context.get("balance", 0)
        lot    = context.get("lot", 0)

        if lot <= 0:
            return RuleResult("REJECT", "Lot zero/missing", priority=self.priority())
        if lot < self._min_lot:
            return RuleResult("REJECT", f"Lot {lot} < min {self._min_lot}", priority=self.priority())

        max_lot = _max_lot_for_equity(float(equity))
        if lot > max_lot:
            return RuleResult("REJECT",
                f"Lot {lot} > max {max_lot} for equity ${equity:.0f}",
                priority=self.priority())

        return RuleResult("APPROVE", f"Lot {lot} OK (equity ${equity:.0f}, max {max_lot})", priority=self.priority())

    def metadata(self) -> Dict[str, Any]:
        return {"name": "dynamic_lot", "type": "risk", "version": "2.0"}

    def priority(self) -> int: return 20
    def enabled(self) -> bool: return getattr(self, "_enabled", True)
