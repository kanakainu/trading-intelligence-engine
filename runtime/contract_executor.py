"""ContractExecutor — reads ExecutionContract and drives position lifecycle.
No trading decisions made here. Contract is the source of truth.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from runtime.position_state import PositionState
from detectors.common import find_swing_pivots, find_nearest_support, find_nearest_resistance
from runtime.trailing_manager import TrailingManager, TrailingProfile


@dataclass
class ExecutionResult:
    action: str          # none | modify | close
    reason: str
    new_sl: Optional[float] = None
    new_tp: Optional[float] = None
    partial_volume: Optional[float] = None  # for partial close


# Profiles instantiated once at module load — not per tick
_TRAILING_PROFILES = {
    "bystra":     TrailingProfile("bystra",     3.0, 2.5, 1.0, 1.0, 360),
    "aggressive": TrailingProfile("aggressive", 2.0, 0.5, 0.2, 0.2,  30),
    "semi_hft":   TrailingProfile("semi_hft",   1.0, 0.5, 0.2, 0.1,   5),
    # [fix 15-Sep] profil era-2 — manager cuma fallback ATR-offset di sini;
    # SL/BE/trailing real tetap manual_trailing_v2 (manage_sl=False).
    "three_ca":   TrailingProfile("three_ca",   0.5, 1.0, 0.3, 0.3, 300),
    "two_e":      TrailingProfile("two_e",      0.5, 1.0, 0.3, 0.3, 300),
    "riri_scalps_v1": TrailingProfile("riri_scalps_v1", 0.5, 1.5, 0.2, 0.5, 0),
}
_TRAILING_MGR = TrailingManager(_TRAILING_PROFILES)


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
            # 3Ca Smart Cutloss: Close if M5 closed candle breaks C2 range
            if "3Ca" in pos.comment:
                cutloss_lvl = meta.get("cutloss")
                if cutloss_lvl:
                    last_closed = m5_candles[-2]
                    if pos.is_buy:
                        if float(last_closed["close"]) < cutloss_lvl:
                            return ExecutionResult("close", f"3Ca_cutloss_break_low_c2_{cutloss_lvl}")
                    else:
                        if float(last_closed["close"]) > cutloss_lvl:
                            return ExecutionResult("close", f"3Ca_cutloss_break_high_c2_{cutloss_lvl}")

            reversal = self._check_m5_reversal(m5_candles, pos.is_buy)
            if reversal:
                return ExecutionResult("close", f"early_exit_reversal_{reversal}")

        # 4. Trailing stop — module-level instance, not per-tick
        new_sl = _TRAILING_MGR.evaluate(pos, pos.current_price, atr, [])
        if new_sl:
             return ExecutionResult("modify", "trailing_stop", new_sl=new_sl)

        return ExecutionResult("none", "hold")

    def _check_m5_reversal(self, m5_candles: List[Dict], is_buy: bool) -> Optional[str]:
        """
        Check for dangerous reversal pattern on M5 — CLOSED candles only.
        m5_candles[-1] = forming (ignored), m5_candles[-2] = last closed, m5_candles[-3] = prev closed.
        Patterns: bearish/bullish engulfing, consecutive, pinbar (hammer/shooting star).
        """
        if len(m5_candles) < 3:
            return None

        # Only use closed candles — skip m5_candles[-1] (still forming)
        c1 = m5_candles[-3]  # 2 closed candles ago
        c2 = m5_candles[-2]  # last CLOSED candle (confirmed)

        c1_o, c1_c = float(c1["open"]), float(c1["close"])
        c2_o, c2_c = float(c2["open"]), float(c2["close"])
        c2_h, c2_l = float(c2["high"]), float(c2["low"])

        c1_bull = c1_c > c1_o
        c2_bull = c2_c > c2_o

        c1_body = abs(c1_c - c1_o)
        c2_body = abs(c2_c - c2_o)
        c2_range = max(c2_h - c2_l, 1e-9)

        # --- Pinbar detection on last closed candle (c2) ---
        c2_upper_wick = c2_h - max(c2_o, c2_c)
        c2_lower_wick = min(c2_o, c2_c) - c2_l

        if is_buy:
            # Shooting star = danger for LONG (long upper wick, small body near low)
            if c2_upper_wick > c2_range * 0.6 and c2_body < c2_range * 0.3:
                return "shooting_star_pinbar"
        else:
            # Hammer = danger for SHORT (long lower wick, small body near high)
            if c2_lower_wick > c2_range * 0.6 and c2_body < c2_range * 0.3:
                return "hammer_pinbar"

        # --- Engulfing on M5 (closed candles only) ---
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
