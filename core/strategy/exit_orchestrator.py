"""Universal Exit Orchestrator — Adaptive RR optimization & Trailing manager."""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ExitProfile(Enum):
    SCALPER = "scalper"          # High freq, tight trail, low RR target (1.0-1.5)
    TREND   = "trend_follower"   # Low freq, wide trail, high RR target (2.0-5.0)
    DEFAULT = "default"

@dataclass
class OptimizedExit:
    sl: float
    tp: float
    rr: float
    trailing_type: str
    adjusted: bool

class ExitOrchestrator:
    def __init__(self, min_gate_rr: float = 1.5):
        self.min_gate_rr = min_gate_rr
        # Config per profile
        self.profiles = {
            ExitProfile.SCALPER: {"target_rr": 1.2, "trail": "structure_m1", "partial_exit": 0.5},
            ExitProfile.TREND:   {"target_rr": 2.5, "trail": "structure_m5", "partial_exit": 0.3},
            ExitProfile.DEFAULT: {"target_rr": 1.5, "trail": "fixed",        "partial_exit": 0.0}
        }

    def optimize(self, strategy_id: str, symbol: str, entry: float, sl: float, tp: float,
                 direction: Optional[str] = None) -> OptimizedExit:
        # 1. Identify Profile
        profile = self._get_profile_by_strategy(strategy_id)
        config = self.profiles[profile]
        
        # 2. Calculate Raw RR
        sl_dist = abs(entry - sl)
        tp_dist = abs(tp - entry)
        raw_rr = tp_dist / sl_dist if sl_dist > 0 else 0
        
        adjusted = False
        final_sl = sl
        final_tp = tp
        final_rr = raw_rr

        # 3. Adaptive Optimization
        # Jika RR < min_gate_rr (1.5), kita bantu loloskan dengan widening TP
        # Tapi ditandai sebagai 'adjusted' supaya ExitEngine tahu harus trail ketat
        if final_rr < self.min_gate_rr:
            needed_tp_dist = sl_dist * self.min_gate_rr
            # Use explicit direction if provided; fallback to SL-based inference
            # Handle both string and Enum (TradeAction)
            dir_str = direction.value if hasattr(direction, 'value') else str(direction)
            if dir_str and dir_str.upper() == "SELL":
                dir_sign = -1
            elif dir_str and dir_str.upper() == "BUY":
                dir_sign = 1
            else:
                # Fallback: SL position relative to entry determines direction
                # SL > entry = SELL (TP below entry), SL < entry = BUY (TP above entry)
                dir_sign = -1 if sl > entry else 1
            
            final_tp = entry + (needed_tp_dist * dir_sign)
            final_rr = self.min_gate_rr
            adjusted = True
            logger.info(f"[{strategy_id}] RR optimized: {raw_rr:.2f} -> {final_rr:.2f} (Widened TP for Gate, dir={direction}, dir_sign={dir_sign})")

        return OptimizedExit(
            sl=round(final_sl, 5),
            tp=round(final_tp, 5),
            rr=round(final_rr, 2),
            trailing_type=config["trail"],
            adjusted=adjusted
        )

    def _get_profile_by_strategy(self, strategy_id: str) -> ExitProfile:
        strategy_id_lower = strategy_id.lower()
        if "hft" in strategy_id_lower or "scalp" in strategy_id_lower:
            return ExitProfile.SCALPER
        if "bystra" in strategy_id_lower or "trend" in strategy_id_lower:
            return ExitProfile.TREND
        return ExitProfile.DEFAULT
