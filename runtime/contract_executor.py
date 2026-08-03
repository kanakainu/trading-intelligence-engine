"""ContractExecutor — reads ExecutionContract and drives position lifecycle.
No trading decisions made here. Contract is the source of truth.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from runtime.position_state import PositionState
from detectors.common import find_swing_pivots, find_nearest_support, find_nearest_resistance


@dataclass
class ExecutionResult:
    action: str          # none | modify | close
    reason: str
    new_sl: Optional[float] = None
    new_tp: Optional[float] = None
    partial_volume: Optional[float] = None  # for partial close


class ContractExecutor:
    """
    Evaluates a live PositionState against the Execution Contract parameters.
    Returns ExecutionResult — no broker calls, no decisions.
    """

    def evaluate(self, pos: PositionState, contract: Any, atr: float,
                 candles: Optional[List[Dict]] = None,
                 m5_candles: Optional[List[Dict]] = None) -> ExecutionResult:
        """
        contract must have: be_trigger_atr, trail_trigger_atr, trail_offset_atr,
        partial_tp_pct, early_exit_reversal (all in metadata or as direct fields).

        If candles provided, trailing stop uses market structure levels
        (support/resistance) with ATR buffer. Falls back to ATR-offset trail.
        """
        meta = getattr(contract, "metadata", {}) or {}
        be_atr_mult    = meta.get("be_trigger_atr", 1.0)
        trail_atr_mult = meta.get("trail_trigger_atr", 1.5)  # faster lock
        trail_offset   = meta.get("trail_offset_atr", 0.5)
        be_buffer      = meta.get("be_buffer_pts", 0.0)
        partial_tp_pct = meta.get("partial_tp_pct", 0.5)  # close 50% at target
        early_exit     = meta.get("early_exit_reversal", True)

        profit = pos.profit_pts
        direction = 1 if pos.is_buy else -1

        # 1. Partial TP trigger - close portion at partial_tp_pct of TP distance
        if partial_tp_pct and pos.take_profit and pos.entry_price:
            tp_dist = abs(pos.take_profit - pos.entry_price)
            if tp_dist > 0 and profit >= tp_dist * partial_tp_pct:
                return ExecutionResult(
                    "close", f"partial_tp_{int(partial_tp_pct*100)}pct",
                    partial_volume=pos.volume * partial_tp_pct
                )

        # 2. Breakeven trigger - faster (1.0 ATR)
        if atr > 0 and profit >= be_atr_mult * atr:
            be_sl = pos.entry_price + (be_buffer * direction)
            be_sl = round(be_sl, 6)
            sl_improves = (
                (pos.is_buy  and be_sl > (pos.stop_loss or float("-inf"))) or
                (not pos.is_buy and be_sl < (pos.stop_loss or float("inf")))
            )
            if sl_improves:
                return ExecutionResult("modify", "breakeven", new_sl=be_sl)

        # 3. Early Exit - dangerous reversal pattern on M5 (NOT M1)
        if early_exit and m5_candles and len(m5_candles) >= 3:
            reversal = self._check_m5_reversal(m5_candles, pos.is_buy)
            if reversal:
                return ExecutionResult("close", f"early_exit_reversal_{reversal}")

        # 4. Trailing stop trigger — using TrailingManager (Money-based Torto Logic)
        from runtime.trailing_manager import TrailingManager, TrailingProfile
        
        # Define profiles based on Torto V4 design (V3 = $3 start, manual = $5 start)
        profiles = {
            "bystra": TrailingProfile("bystra", 3.0, 2.5, 1.0, 1.0, 360),
            "aggressive": TrailingProfile("aggressive", 3.0, 1.5, 0.5, 0.5, 30),
            "semi_hft": TrailingProfile("semi_hft", 3.0, 0.5, 0.2, 0.3, 5),
        }
        trailing_mgr = TrailingManager(profiles)
        
        new_sl = trailing_mgr.evaluate(pos, pos.current_price, atr, [])
        if new_sl:
             return ExecutionResult("modify", "trailing_stop", new_sl=new_sl)

        return ExecutionResult("none", "hold")

    def _check_m5_reversal(self, m5_candles: List[Dict], is_buy: bool) -> Optional[str]:
        """
        Check for dangerous reversal pattern on M5 (closed candles only).
        Returns pattern name if detected, else None.
        Ignores M1 noise per Mas'ku requirement.
        """
        if len(m5_candles) < 3:
            return None
        
        # Use last 2 CLOSED candles + current forming
        c1 = m5_candles[-3]  # 2 candles ago
        c2 = m5_candles[-2]  # 1 candle ago (closed)
        curr = m5_candles[-1]  # forming
        
        c1_o, c1_c = float(c1["open"]), float(c1["close"])
        c2_o, c2_c = float(c2["open"]), float(c2["close"])
        
        c1_bull = c1_c > c1_o
        c2_bull = c2_c > c2_o
        
        c1_body = abs(c1_c - c1_o)
        c2_body = abs(c2_c - c2_o)
        
        # Engulfing on M5 (closed candles only)
        if is_buy:
            # Bearish engulfing = danger for LONG
            if c1_bull and not c2_bull:
                if c2_o >= c1_c and c2_c <= c1_o and c2_body > c1_body * 1.2:
                    return "bearish_engulfing"
            # Two consecutive strong bearish
            if not c1_bull and not c2_bull and c1_body > c2_body * 0.8:
                return "consecutive_bearish"
        else:
            # Bullish engulfing = danger for SHORT
            if not c1_bull and c2_bull:
                if c2_o <= c1_c and c2_c >= c1_o and c2_body > c1_body * 1.2:
                    return "bullish_engulfing"
            # Two consecutive strong bullish
            if c1_bull and c2_bull and c1_body > c2_body * 0.8:
                return "consecutive_bullish"
        
        return None
