"""DynamicLotPlugin — tiered fixed lot by equity/balance."""
from typing import Any, Dict
from core.rules.plugins.plugin_interface import RulePluginInterface, RuleResult

# tiered fixed lot by equity/balance (user-tuned 2026-08-21)
EQUITY_TIERS = [
    (10,    200,   0.01),  # Micro: $10 - $200
    (201,   750,   0.05),  # Low: $201 - $750 (Boskuh here)
    (751,   1500,  0.10),  # Mid: $751 - $1500
    (1501,  5000,  0.25),  # High
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
