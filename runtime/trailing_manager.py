"""TrailingManager — handles adaptive money-based trailing stops for live positions.
Contek dari manual_trailing.py yang terbukti jalan (Torto V4 logic).
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from runtime.position_state import PositionState

log = logging.getLogger("TrailingManager")

@dataclass
class TrailingProfile:
    strategy_id: str
    min_profit_usd_start_trail: float  # e.g., $2 for aggressive, $1 for semi_hft
    trail_distance_usd: float          # e.g., $0.5
    trail_step_usd: float              # e.g., $0.2
    min_rr_breakeven_trigger: float    # e.g. 0.2R for aggressive, 0.1R for semi_hft
    time_exit_minutes: Optional[int] = None

# Global peak tracker (ticket → peak_profit)
_peak: Dict[str, float] = {}

class TrailingManager:
    """Manages dynamic trailing stops for a single position or group of positions.
    Logic contek dari manual_trailing.py (line 41-90) yang terbukti jalan.
    """

    def __init__(self, profiles: Dict[str, TrailingProfile]):
        self._profiles = profiles
        log.info(f"TrailingManager initialized with {len(profiles)} profiles.")

    def evaluate(self, pos: PositionState, current_price: float, atr: float, open_positions_for_symbol: List[PositionState]) -> Optional[float]:
        """
        Evaluates position for trailing stop adjustment.
        Returns new_sl if adjustment needed, else None.

        Trail logic (contek manual_trailing.py):
        Phase 1: profit >= START → lock SL to Entry + offset
        Phase 2: profit pullback from peak → lock (peak - DIST)
        """
        profile = self._get_profile_for_position(pos)
        if not profile:
            log.warning(f"No trailing profile for strategy: {pos.strategy_id}")
            return None

        profit_usd = pos.unrealized_profit
        entry = pos.entry_price
        current = pos.current_price
        sl = pos.stop_loss or 0.0
        direction_str = "buy" if pos.is_buy else "sell"
        is_buy = pos.is_buy
        ticket = pos.position_id

        # Minimal validation
        if profit_usd < profile.min_profit_usd_start_trail:
            return None

        if current == entry or profit_usd == 0:
            return None

        # KEY FORMULA dari manual_trailing.py line 60
        pts_per_usd = abs(current - entry) / abs(profit_usd)

        # Phase 1: Profit lock — move SL to Entry + offset if profit >= START
        be_lock_offset = 1.5  # manual_trailing.py line 64
        be_sl = entry + (be_lock_offset if is_buy else -be_lock_offset)

        if sl == 0.0 or (is_buy and sl < be_sl) or (not is_buy and sl > be_sl):
            log.info(f"[{ticket}] BE lock: SL {sl} → {be_sl:.2f} | profit ${profit_usd:.2f}")
            return round(be_sl, 2)

        # Phase 2: Dynamic trail based on peak profit pullback
        if ticket not in _peak:
            _peak[ticket] = profit_usd
        elif profit_usd > _peak[ticket]:
            _peak[ticket] = profit_usd

        peak_profit = _peak[ticket]

        if profit_usd >= peak_profit:
            return None  # still rising, no trail move yet

        lock_floor = peak_profit - profile.trail_distance_usd

        if lock_floor <= 0:
            return None

        # KEY FORMULA dari manual_trailing.py line 79-90
        sl_price_offset = lock_floor * pts_per_usd

        if is_buy:
            new_sl = entry + sl_price_offset
            if new_sl <= sl + profile.trail_step_usd * pts_per_usd:
                return None
            log.info(f"[{ticket}] Trail: profit ${profit_usd:.2f} peak ${peak_profit:.2f} locked ${lock_floor:.2f} → SL {new_sl:.2f}")
            return round(new_sl, 2)
        else:
            new_sl = entry - sl_price_offset
            if new_sl >= sl - profile.trail_step_usd * pts_per_usd:
                return None
            log.info(f"[{ticket}] Trail: profit ${profit_usd:.2f} peak ${peak_profit:.2f} locked ${lock_floor:.2f} → SL {new_sl:.2f}")
            return round(new_sl, 2)

    def _get_profile_for_position(self, pos: PositionState) -> Optional[TrailingProfile]:
        return self._profiles.get(pos.strategy_id)

def cleanup_peak(ticket: str):
    """Remove peak tracker when position closes."""
    if ticket in _peak:
        del _peak[ticket]
