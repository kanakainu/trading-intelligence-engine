"""Trade Planner — Calculate SL/TP/DZ/RR from FusedSignal + MarketContext.

Moves ALL risk calculation logic OUT of Strategy Orchestrator.
Orchestrator becomes pure coordinator.
"""
from typing import Optional, Dict, List
from core.planner.planner_models import TradePlan, PlannerInputs


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
        entry_mid = (entry_zone["low"] + entry_zone["high"]) / 2
        
        # 1. Danger Zone
        danger_zone = self._calc_danger_zone(inputs)
        
        # 2. Stop Loss
        sl = self._calc_stop_loss(inputs)
        
        # 3. Take Profit
        tp = self._calc_take_profit(inputs, sl, entry_mid)
        
        # 4. Risk/Reward
        risk_points, reward_points, rr = self._calc_risk_reward(
            direction=direction,
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
        
        if inputs.direction == "sell" and inputs.h1_resistance:
            return float(inputs.h1_resistance)
        elif inputs.direction == "buy" and inputs.h1_support:
            return float(inputs.h1_support)
        
        return None
    
    def _calc_stop_loss(self, inputs: PlannerInputs) -> Optional[float]:
        """
        SL from entry_tf swing pivots OUTSIDE entry_zone.
        
        SELL: SL = lowest swing HIGH above entry_zone['high']
        BUY: SL = highest swing LOW below entry_zone['low']
        """
        direction = inputs.direction
        entry_zone = inputs.entry_zone
        entry_tf = inputs.timeframe
        
        # Detector override
        if inputs.detector_sl is not None:
            return float(inputs.detector_sl)
        
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
                    return swing_highs[0] + buf
            else:
                # SL below entry_zone low
                ez_ref = float(entry_zone["low"])
                swing_lows = sorted([p["price"] for p in pivots if p["type"] == "low" and p["price"] < ez_ref], reverse=True)
                if swing_lows:
                    return swing_lows[0] - buf
        
        return None
    
    def _calc_take_profit(self, inputs: PlannerInputs, sl: Optional[float], entry_mid: float) -> Optional[float]:
        """
        TP from nearest H1 S/R with min 1.5 RR.
        Fallback: entry ± risk × 1.5
        """
        direction = inputs.direction
        entry_zone = inputs.entry_zone
        h1_support = inputs.h1_support
        h1_resistance = inputs.h1_resistance
        atr = inputs.atr
        
        if not sl:
            # No SL → ATR-based TP
            return entry_mid + atr * 1.5 if direction == "buy" else entry_mid - atr * 1.5
        
        # Calculate risk
        if direction == "sell":
            risk = float(sl) - float(entry_zone["low"])
            if h1_support:
                tp_val = float(h1_support)
                reward = float(entry_zone["low"]) - tp_val
                if reward >= risk * 1.5:
                    return tp_val
            # Fallback
            return entry_mid - risk * 1.5
        else:
            risk = float(entry_zone["high"]) - float(sl)
            if h1_resistance:
                tp_val = float(h1_resistance)
                reward = tp_val - float(entry_zone["high"])
                if reward >= risk * 1.5:
                    return tp_val
            # Fallback
            return entry_mid + risk * 1.5
    
    def _calc_risk_reward(
        self,
        direction: str,
        entry_zone: Dict[str, float],
        sl: Optional[float],
        tp: Optional[float]
    ) -> tuple:
        """Calculate risk_points, reward_points, RR ratio."""
        if not sl or not tp:
            return 0.0, 0.0, 0.0
        
        if direction == "sell":
            risk_points = abs(float(sl) - float(entry_zone["low"]))
            reward_points = abs(float(entry_zone["low"]) - float(tp))
        else:
            risk_points = abs(float(entry_zone["high"]) - float(sl))
            reward_points = abs(float(tp) - float(entry_zone["high"]))
        
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