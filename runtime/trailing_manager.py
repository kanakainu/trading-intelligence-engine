"""TrailingManager — handles adaptive money-based trailing stops for live positions."""
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from runtime.position_state import PositionState

log = logging.getLogger("TrailingManager")

@dataclass
class TrailingProfile:
    strategy_id: str
    min_profit_usd_start_trail: float  # e.g., $5 for single, $7.5 for group
    trail_distance_usd: float          # e.g., $2.5 for single, $3.5 for group
    trail_step_usd: float              # e.g., $1 for single, $1.5 for group
    min_rr_breakeven_trigger: float    # e.g. 1.0 (1R) for Bystra, 0.5 (0.5R) for Aggressive
    time_exit_minutes: Optional[int] = None # e.g. 30 for Scalper, 360 for Swing

class TrailingManager:
    """Manages dynamic trailing stops for a single position or group of positions."""

    def __init__(self, profiles: Dict[str, TrailingProfile]):
        self._profiles = profiles
        log.info(f"TrailingManager initialized with {len(profiles)} profiles.")

    def evaluate(self, pos: PositionState, current_price: float, atr: float, open_positions_for_symbol: List[PositionState]) -> Optional[float]:
        """
        Evaluates position for trailing stop adjustment.
        Returns new_sl if adjustment needed, else None.
        """
        profile = self._get_profile_for_position(pos)
        if not profile:
            log.warning(f"No trailing profile for strategy: {pos.strategy_id}")
            return None
        
        # Determine if single, group, or hedge
        # For now, focus on single position trailing. Group/Hedge will be added later.
        
        profit_usd = pos.unrealized_profit # This is in USD from broker (or converted)

        # 1. Breakeven Trigger (using RR from position initial setup)
        if pos.profit_pts > 0 and pos.rr > 0 and (profit_usd / (pos.sl_dist_pts * pos.point_value)) >= profile.min_rr_breakeven_trigger:
            if pos.stop_loss is None or (pos.is_buy and pos.entry_price > pos.stop_loss) or (not pos.is_buy and pos.entry_price < pos.stop_loss):
                new_sl = pos.entry_price # Move SL to entry
                log.info(f"[{pos.position_id}] Trailing: Breakeven triggered. SL set to {new_sl}")
                return new_sl

        # 2. Money-based Trailing (after breakeven, or if no fixed SL)
        if profit_usd >= profile.min_profit_usd_start_trail:
            # Calculate new SL based on trail_distance_usd and trail_step_usd
            # This is a simplified money-based trailing. More complex logic (step-by-step) can be added.
            sl_move_amount_usd = profit_usd - profile.trail_distance_usd # Example: if profit is $10, trail_dist is $5, new SL should be at $5 profit

            if sl_move_amount_usd > 0: # Only trail if still in profit after offset
                # Convert USD profit to price points
                sl_move_pts = sl_move_amount_usd / pos.point_value # pos.point_value needed from broker/symbol info
                
                if pos.is_buy:
                    new_sl = current_price - sl_move_pts
                else:
                    new_sl = current_price + sl_move_pts
                
                # Only update if new_sl is better (higher for buy, lower for sell)
                if pos.stop_loss is None or \
                   (pos.is_buy and new_sl > pos.stop_loss) or \
                   (not pos.is_buy and new_sl < pos.stop_loss):
                    log.info(f"[{pos.position_id}] Trailing: Profit {profit_usd:.2f} USD. SL set to {new_sl:.2f}")
                    return round(new_sl, pos.digits) # Round to symbol digits
        
        return None

    def _get_profile_for_position(self, pos: PositionState) -> Optional[TrailingProfile]:
        # Logic to map pos.strategy_id to a TrailingProfile
        # For now, direct lookup. Later, can be more complex (e.g., from config)
        return self._profiles.get(pos.strategy_id)

