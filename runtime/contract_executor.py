"""ContractExecutor — reads ExecutionContract and drives position lifecycle.
No trading decisions made here. Contract is the source of truth.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional
from runtime.position_state import PositionState


@dataclass
class ExecutionResult:
    action: str          # none | modify | close
    reason: str
    new_sl: Optional[float] = None
    new_tp: Optional[float] = None


class ContractExecutor:
    """
    Evaluates a live PositionState against the Execution Contract parameters.
    Returns ExecutionResult — no broker calls, no decisions.
    """

    def evaluate(self, pos: PositionState, contract: Any, atr: float) -> ExecutionResult:
        """
        contract must have: be_trigger_atr, trail_trigger_atr, trail_offset_atr,
        partial_tp_pct (all in metadata or as direct fields).
        """
        meta = getattr(contract, "metadata", {}) or {}
        be_atr_mult    = meta.get("be_trigger_atr", 1.0)
        trail_atr_mult = meta.get("trail_trigger_atr", 2.0)
        trail_offset   = meta.get("trail_offset_atr", 0.5)
        be_buffer      = meta.get("be_buffer_pts", 0.0)
        partial_tp_pct = meta.get("partial_tp_pct", None)

        profit = pos.profit_pts
        direction = 1 if pos.is_buy else -1

        # 1. Partial TP trigger
        if partial_tp_pct and pos.take_profit and pos.entry_price:
            tp_dist = abs(pos.take_profit - pos.entry_price)
            if tp_dist > 0 and profit >= tp_dist * partial_tp_pct:
                return ExecutionResult("close", f"partial_tp_{partial_tp_pct}")

        # 2. Breakeven trigger
        if atr > 0 and profit >= be_atr_mult * atr:
            be_sl = pos.entry_price + (be_buffer * direction)
            be_sl = round(be_sl, 6)
            sl_improves = (
                (pos.is_buy  and be_sl > (pos.stop_loss or float("-inf"))) or
                (not pos.is_buy and be_sl < (pos.stop_loss or float("inf")))
            )
            if sl_improves:
                return ExecutionResult("modify", "breakeven", new_sl=be_sl)

        # 3. Trailing stop trigger
        if atr > 0 and profit >= trail_atr_mult * atr:
            offset = trail_offset * atr
            new_sl = round(pos.current_price - (direction * offset), 6)
            sl_improves = (
                (pos.is_buy  and new_sl > (pos.stop_loss or float("-inf"))) or
                (not pos.is_buy and new_sl < (pos.stop_loss or float("inf")))
            )
            if sl_improves:
                return ExecutionResult("modify", "trailing_stop", new_sl=new_sl)

        return ExecutionResult("none", "hold")
