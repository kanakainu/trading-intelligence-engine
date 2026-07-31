"""Opportunity Engine — Market filter evaluated BEFORE detectors execute.

Generic filter — NO strategy-specific logic.
"""
from datetime import datetime, timezone
from typing import Optional

from core.opportunity.opportunity_models import (
    OpportunitySnapshot, OpportunityInputs, OpportunityDecision, BlockReason
)


class OpportunityEngine:
    """
    Pre-detector market filter.
    
    Blocks detector execution if:
    - Spread too high
    - ADX too low (no trend)
    - News active (regime=NEWS)
    - Low liquidity (regime=LOW_LIQUIDITY)
    - Dead session (Asian low-liquidity hours)
    - ATR below threshold (insufficient volatility)
    
    Priority scale: 0=blocked, 1-10=allowed (higher=better conditions).
    """
    
    # Thresholds (tunable per symbol)
    SPREAD_MAX = {
        "XAUUSD": 0.5,
        "BTCUSD": 50.0,
        "GBPUSD": 0.0005,
    }
    
    ADX_MIN = 15.0  # Below = ranging/choppy, skip
    ATR_PCT_MIN = 0.002  # 0.2% — below = dead market
    
    DEAD_SESSIONS = {
        "ASIAN_DEAD": (2, 6),  # UTC 02:00-06:00 (WIB 09:00-13:00)
    }
    
    def __init__(self):
        pass
    
    def evaluate(self, inputs: OpportunityInputs) -> OpportunitySnapshot:
        """Evaluate market opportunity. Returns ALLOWED or BLOCKED."""
        
        symbol = inputs.symbol
        spread = inputs.spread
        atr_pct = inputs.atr_percent
        vol_ratio = inputs.volume_ratio
        regime_name = inputs.regime_name or "UNKNOWN"
        adx = inputs.adx
        current_time = inputs.current_time or datetime.now(timezone.utc)
        
        # Check filters in priority order
        reason, priority, confidence = self._check_filters(
            symbol=symbol,
            spread=spread,
            atr_pct=atr_pct,
            vol_ratio=vol_ratio,
            regime_name=regime_name,
            adx=adx,
            current_time=current_time,
        )
        
        market_allowed = (reason == BlockReason.NONE)
        
        # Determine session
        hour_utc = current_time.hour
        session = self._get_session(hour_utc)
        
        return OpportunitySnapshot(
            market_allowed=market_allowed,
            reason=reason,
            priority=priority,
            confidence=confidence,
            symbol=symbol,
            timestamp=current_time,
            scan_id=inputs.scan_id,
            spread=spread,
            atr_pct=atr_pct,
            adx=adx,
            volume_ratio=vol_ratio,
            session=session,
        )
    
    def _check_filters(
        self,
        symbol: str,
        spread: float,
        atr_pct: float,
        vol_ratio: float,
        regime_name: str,
        adx: float,
        current_time: datetime,
    ) -> tuple:
        """Check all filters. Returns (reason, priority, confidence)."""
        
        # 1. Spread check
        max_spread = self.SPREAD_MAX.get(symbol, 1.0)
        if spread > max_spread:
            return (BlockReason.SPREAD_HIGH, 0, 0.9)
        
        # 2. Dead session check
        hour_utc = current_time.hour
        if self._is_dead_session(hour_utc):
            return (BlockReason.DEAD_SESSION, 0, 0.85)
        
        # 3. Low liquidity regime check
        if regime_name == "LOW_LIQUIDITY":
            return (BlockReason.LOW_LIQUIDITY, 0, 0.9)
        
        # 4. News active regime check
        if regime_name == "NEWS":
            return (BlockReason.NEWS_ACTIVE, 0, 0.9)
        
        # 5. ATR too low check
        if atr_pct < self.ATR_PCT_MIN:
            return (BlockReason.ATR_LOW, 0, 0.8)
        
        # 6. ADX too low check (no trend)
        if adx < self.ADX_MIN:
            return (BlockReason.ADX_LOW, 0, 0.75)
        
        # ALLOWED — compute priority
        priority = self._compute_priority(
            spread=spread,
            atr_pct=atr_pct,
            vol_ratio=vol_ratio,
            adx=adx,
            regime_name=regime_name,
            max_spread=max_spread,
        )
        
        confidence = 0.8  # Base confidence for allowed
        
        return (BlockReason.NONE, priority, confidence)
    
    def _is_dead_session(self, hour_utc: int) -> bool:
        """Check if current hour falls in dead session."""
        for session_name, (start, end) in self.DEAD_SESSIONS.items():
            if start <= hour_utc < end:
                return True
        return False
    
    def _get_session(self, hour_utc: int) -> str:
        """Get session name from UTC hour."""
        if 0 <= hour_utc < 8:
            return "ASIAN"
        elif 8 <= hour_utc < 16:
            return "LONDON"
        elif 16 <= hour_utc < 24:
            return "NY"
        return "UNKNOWN"
    
    def _compute_priority(
        self,
        spread: float,
        atr_pct: float,
        vol_ratio: float,
        adx: float,
        regime_name: str,
        max_spread: float,
    ) -> int:
        """Compute priority 1-10 (higher=better)."""
        
        score = 0
        
        # Spread quality (0-3 points)
        spread_ratio = spread / max_spread
        if spread_ratio < 0.3:
            score += 3
        elif spread_ratio < 0.6:
            score += 2
        else:
            score += 1
        
        # ATR quality (0-3 points)
        if atr_pct > 0.01:  # 1%+
            score += 3
        elif atr_pct > 0.005:  # 0.5-1%
            score += 2
        else:
            score += 1
        
        # ADX/trend quality (0-2 points)
        if adx > 40:
            score += 2
        elif adx > 25:
            score += 1
        
        # Regime bonus (0-2 points)
        if regime_name in ("TRENDING", "STRONG_TREND"):
            score += 2
        elif regime_name == "EARLY_TREND":
            score += 1
        
        return min(score, 10)


# Global engine instance
_global_engine: Optional[OpportunityEngine] = None


def get_opportunity_engine() -> OpportunityEngine:
    """Get or create global opportunity engine."""
    global _global_engine
    if _global_engine is None:
        _global_engine = OpportunityEngine()
    return _global_engine


def evaluate_opportunity(inputs: OpportunityInputs) -> OpportunitySnapshot:
    """Convenience function: evaluate using global engine."""
    engine = get_opportunity_engine()
    return engine.evaluate(inputs)