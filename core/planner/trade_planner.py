"""Trade Planner — Calculate SL/TP/DZ/RR from FusedSignal + MarketContext.

Moves ALL risk calculation logic OUT of Strategy Orchestrator.
Orchestrator becomes pure coordinator.
"""
from typing import Optional, Dict, List
import logging
from core.planner.planner_models import TradePlan, PlannerInputs

logger = logging.getLogger(__name__)


class TradePlanner:
    """
    Pure risk calculator.
    
    Input: FusedSignal + MarketContext
    Output: TradePlan (Entry + SL + TP + DZ + RR + Position)
    
    NO execution.
    NO strategy logic.
    """
    
    def __init__(self):
        pass
    
    def plan(self, inputs: PlannerInputs) -> TradePlan:
        """Build complete trade plan."""
        symbol = inputs.symbol
        direction = inputs.direction
        entry_zone = inputs.entry_zone
        
        # Handle single-point entry_zone (if only 'low' or 'high' is provided)
        if "low" in entry_zone and "high" in entry_zone:
            entry_mid = (entry_zone["low"] + entry_zone["high"]) / 2
        elif "low" in entry_zone:
            entry_mid = entry_zone["low"]
        elif "high" in entry_zone:
            entry_mid = entry_zone["high"]
        else:
            # Fallback for safety, though should not happen if signal is valid
            entry_mid = inputs.current_price

        # 1. Danger Zone
        danger_zone = self._calc_danger_zone(inputs)
        
        # 2. Stop Loss
        sl = self._calc_stop_loss(inputs, entry_mid)
        
        # 3. Take Profit
        tp = self._calc_take_profit(inputs, sl, entry_mid)

        # FINAL SANITY CHECK: Protect against negative/insane SL/TP (XAUUSD focus)
        # If SL/TP is suspiciously low or negative, block the plan
        if sl is not None and sl < 1000.0:
            logger.error(f"PLAN REJECTED: Insane SL detected ({sl}). EntryMid={entry_mid}")
            return None
        if tp is not None and tp < 1000.0:
            logger.error(f"PLAN REJECTED: Insane TP detected ({tp}). EntryMid={entry_mid}")
            return None
        
        # 4. Risk/Reward
        risk_points, reward_points, rr = self._calc_risk_reward(
            direction_str=direction,
            entry_zone=entry_zone,
            sl=sl,
            tp=tp
        )
        
        # 5. Position Size
        position_size, position_risk_pct = self._calc_position_size(
            risk_points=risk_points,
            balance=inputs.balance,
            risk_pct=inputs.risk_per_trade_pct,
            symbol=symbol
        )
        
        # Build metadata
        metadata = {
            "h1_support": inputs.h1_support,
            "h1_resistance": inputs.h1_resistance,
            "detector_dz": inputs.detector_danger_zone,
            "detector_sl": inputs.detector_sl,
            "spread_buffer": inputs.spread_buffer,
            "atr": inputs.atr,
            "strategies": inputs.strategies,
        }
        
        plan_id = f"plan_{symbol}_{inputs.scan_id}_{int(inputs.timestamp.timestamp())}"
        
        return TradePlan(
            plan_id=plan_id,
            symbol=symbol,
            direction=direction,
            entry_zone=entry_zone,
            entry_mid=entry_mid,
            sl=sl,
            tp=tp,
            danger_zone=danger_zone,
            risk_reward=rr,
            risk_points=risk_points,
            reward_points=reward_points,
            position_size=position_size,
            position_risk_pct=position_risk_pct,
            timeframe=inputs.timeframe,
            strategy=",".join(inputs.strategies) if inputs.strategies else "UNKNOWN",
            confidence=inputs.confidence,
            metadata=metadata,
            created_at=inputs.timestamp,
        )
    
    def _calc_danger_zone(self, inputs: PlannerInputs) -> Optional[float]:
        """
        DZ priority:
        1. Detector-specific DZ (per-setup structural invalidation)
        2. H1 S/R (generic)
        """
        if inputs.detector_danger_zone is not None:
            return float(inputs.detector_danger_zone)
        
        if str(inputs.direction).lower() == "sell" and inputs.h1_resistance:
            return float(inputs.h1_resistance)
        elif str(inputs.direction).lower() == "buy" and inputs.h1_support:
            return float(inputs.h1_support)
        
        return None
    
    def _calc_stop_loss(self, inputs: PlannerInputs, entry_mid: float) -> float:
        """
        SL from entry_tf swing pivots OUTSIDE entry_zone.
        
        SELL: SL = lowest swing HIGH above entry_zone['high']
        BUY: SL = highest swing LOW below entry_zone['low']
        """
        direction = str(inputs.direction).lower()  # normalize case
        entry_zone = inputs.entry_zone
        entry_tf = inputs.timeframe
        
        # Detector override (with direction guard)
        if inputs.detector_sl is not None and entry_zone:
            sl = float(inputs.detector_sl)
            ez_ref = float(entry_zone.get("high") if direction == "sell" else entry_zone.get("low"))
            # SELL: SL must be ABOVE entry; BUY: SL must be BELOW entry
            if (direction == "sell" and sl > ez_ref) or (direction == "buy" and sl < ez_ref):
                return sl
            logger.warning("detector_sl %.2f wrong direction for %s (entry ref %.2f) — ignoring", sl, direction, ez_ref)
        
        buf = max(inputs.spread_buffer / 10, 0.25)
        
        # Try entry_tf first, fallback H1
        for tf_key in [entry_tf, "H1"]:
            tf_candles = inputs.candles.get(tf_key, [])
            if not tf_candles:
                continue
            
            pivots = self._find_swing_pivots(tf_candles)
            
            if direction == "sell":
                        # SL above entry_zone high
                ez_ref = float(entry_zone["high"])
                swing_highs = sorted([p["price"] for p in pivots if p["type"] == "high" and p["price"] > ez_ref])
                if swing_highs:
                    return swing_highs[0] + 0.0 # buf replaced with 0.0
            else:
                # SL below entry_zone low
                ez_ref = float(entry_zone["low"])
                swing_lows = sorted([p["price"] for p in pivots if p["type"] == "low" and p["price"] < ez_ref], reverse=True)
                if swing_lows:
                    return swing_lows[0] - 0.0 # buf replaced with 0.0
        
        # FALLBACK: ATR buffer — never return None (order with no SL = naked risk)
        atr = float(getattr(inputs, "atr", 0.0) or 5.0)
        atr_buf = atr * 0.5  # scalping: tight SL
        if direction == "sell":
            return float(entry_mid) + atr_buf
        return float(entry_mid) - atr_buf
    
    def _calc_take_profit(self, inputs: PlannerInputs, sl: Optional[float], entry_mid: float) -> Optional[float]:
        """
        TP from nearest H1 S/R with min 1.5 RR.
        Fallback: entry ± risk × 1.5
        """
        direction = str(inputs.direction).lower() # normalize case
        entry_zone = inputs.entry_zone
        h1_support = inputs.h1_support
        h1_resistance = inputs.h1_resistance
        atr = inputs.atr

        if not sl:
            # No SL → ATR-based TP
            return entry_mid + atr * 1.5 if direction == "buy" else entry_mid - atr * 1.5

        # Calculate risk using entry_mid (fallback safe)
        if direction == "sell":
            risk = float(sl) - float(entry_mid)
            # Use H1 support if valid and provides good RR
            if h1_support and h1_support > 0.0 and (entry_mid - h1_support) >= risk * 1.5:
                return h1_support
            # Fallback
            return entry_mid - risk * 1.5
        else: # direction == "buy"
            risk = float(entry_mid) - float(sl)
            # Use H1 resistance if valid and provides good RR
            if h1_resistance and h1_resistance < 999999.0 and (h1_resistance - entry_mid) >= risk * 1.5:
                return h1_resistance
            # Fallback
            return entry_mid + risk * 1.5

    def _calc_risk_reward(
        self,
        direction_str: str, # Use a different var name to avoid collision
        entry_zone: Dict[str, float],
        sl: Optional[float],
        tp: Optional[float]
    ) -> tuple:
        """
        Calculate risk_points, reward_points, RR ratio.
        Direction_str is normalized to lowercase.
        """
        direction = direction_str.lower() # normalize case
        if not sl or not tp:
            return 0.0, 0.0, 0.0
        
        # Use entry_mid for safe calculation
        entry_mid = 0.0
        if "low" in entry_zone and "high" in entry_zone:
            entry_mid = (entry_zone["low"] + entry_zone["high"]) / 2
        elif "low" in entry_zone:
            entry_mid = entry_zone["low"]
        elif "high" in entry_zone:
            entry_mid = entry_zone["high"]
        
        if direction == "sell":
            risk_points = abs(float(sl) - float(entry_mid))
            reward_points = abs(float(entry_mid) - float(tp))
        else: # direction == "buy"
            risk_points = abs(float(entry_mid) - float(sl))
            reward_points = abs(float(tp) - float(entry_mid))

        rr = reward_points / risk_points if risk_points > 0 else 0.0
        return risk_points, reward_points, rr
    
    def _calc_position_size(
        self,
        risk_points: float,
        balance: float,
        risk_pct: float,
        symbol: str
    ) -> tuple:
        """Calculate lot size from risk parameters."""
        # Risk amount
        risk_amount = balance * (risk_pct / 100)
        
        # Lot size calculation (symbol-specific)
        if symbol == "XAUUSD":
            # 1 lot = $100/point
            lot_size = risk_amount / (risk_points * 100) if risk_points > 0 else 0.01
        elif symbol == "BTCUSD":
            # 1 lot = $1/point
            lot_size = risk_amount / risk_points if risk_points > 0 else 0.01
        else:
            # Generic forex
            lot_size = risk_amount / (risk_points * 100000) if risk_points > 0 else 0.01
        
        # Clamp to min 0.01
        lot_size = max(lot_size, 0.01)
        
        # Position risk % (actual)
        actual_risk_pct = (risk_points * lot_size * 100 / balance) if balance > 0 else risk_pct
        
        return round(lot_size, 2), round(actual_risk_pct, 2)
    
    def _find_swing_pivots(self, candles: List[Dict], n: int = 2) -> List[Dict]:
        """Find swing pivots (highs/lows) with n-bar lookback."""
        pivots = []
        if len(candles) < n * 2 + 1:
            return pivots
        
        for i in range(n, len(candles) - n):
            c = candles[i]
            h, l = float(c["high"]), float(c["low"])
            
            # Check swing high
            is_high = all(h >= float(candles[j]["high"]) for j in range(i - n, i + n + 1) if j != i)
            if is_high:
                pivots.append({"type": "high", "price": h, "index": i})
            
            # Check swing low
            is_low = all(l <= float(candles[j]["low"]) for j in range(i - n, i + n + 1) if j != i)
            if is_low:
                pivots.append({"type": "low", "price": l, "index": i})
        
        return pivots


# Global instance
_global_planner: Optional[TradePlanner] = None


def get_trade_planner() -> TradePlanner:
    global _global_planner
    if _global_planner is None:
        _global_planner = TradePlanner()
    return _global_planner


def build_trade_plan(inputs: PlannerInputs) -> TradePlan:
    """Convenience function."""
    planner = get_trade_planner()
    return planner.plan(inputs)