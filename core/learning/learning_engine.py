"""Learning Engine — Post-trade reflection and analytics.

NO LLM. Pure statistical analysis.
HCK-ready: outputs structured JSON for future LLM interpretation.
"""
from typing import List, Dict, Optional, Any
from collections import defaultdict
from core.learning.learning_models import (
    TradeReflection, PerformanceMetrics, TradeOutcome, ExitReason
)


class LearningEngine:
    """
    Post-trade analytics engine.
    
    Input: Closed trade + TradePlan + Context
    Output: TradeReflection + PerformanceMetrics
    
    NO strategy logic.
    NO LLM calls.
    Pure statistics.
    """
    
    def __init__(self):
        self._reflections: List[TradeReflection] = []
    
    def reflect(
        self,
        trade_id: str,
        symbol: str,
        strategy: str,
        outcome: TradeOutcome,
        exit_reason: ExitReason,
        realized_pl: float,
        risk_amount: float,
        rr_planned: float,
        duration_seconds: float,
        entry_time,
        exit_time,
        entry_regime: str,
        entry_confidence: float,
        opportunity_priority: int,
        exit_regime: str,
        exit_price: float,
        entry_price: float,
        sl_price: Optional[float],
        tp_price: Optional[float],
        max_favorable_excursion: float,
        max_adverse_excursion: float,
        entry_features: Dict[str, Any],
        metadata: Dict[str, Any] = None  # type: ignore[assignment]
    ) -> TradeReflection:
        """Create reflection from closed trade."""
        # Calculate metrics
        realized_pl_pct = (realized_pl / risk_amount * 100) if risk_amount > 0 else 0.0
        rr_actual = (realized_pl / risk_amount) if risk_amount > 0 else 0.0
        efficiency = (realized_pl / max_favorable_excursion) if max_favorable_excursion > 0 else 0.0
        
        reflection = TradeReflection(
            reflection_id=f"refl_{trade_id}",
            trade_id=trade_id,
            symbol=symbol,
            strategy=strategy,
            outcome=outcome,
            exit_reason=exit_reason,
            realized_pl=realized_pl,
            realized_pl_pct=realized_pl_pct,
            risk_amount=risk_amount,
            rr_actual=rr_actual,
            rr_planned=rr_planned,
            duration_seconds=duration_seconds,
            entry_time=entry_time,
            exit_time=exit_time,
            entry_regime=entry_regime,
            entry_confidence=entry_confidence,
            opportunity_priority=opportunity_priority,
            exit_regime=exit_regime,
            exit_price=exit_price,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            max_favorable_excursion=max_favorable_excursion,
            max_adverse_excursion=max_adverse_excursion,
            efficiency=efficiency,
            entry_features=entry_features,
            metadata=metadata or {}
        )
        
        self._reflections.append(reflection)
        return reflection
    
    def compute_metrics(self, period_start=None, period_end=None) -> PerformanceMetrics:
        """Compute aggregate performance metrics."""
        reflections = self._reflections
        
        if not reflections:
            return PerformanceMetrics(
                total_trades=0,
                win_count=0,
                loss_count=0,
                breakeven_count=0,
                win_rate=0.0,
                total_pl=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                largest_win=0.0,
                largest_loss=0.0,
                avg_rr_actual=0.0,
                avg_rr_planned=0.0,
                avg_efficiency=0.0,
                avg_duration_seconds=0.0
            )
        
        # Filter by period if specified
        if period_start or period_end:
            reflections = [
                r for r in reflections
                if (not period_start or r.entry_time >= period_start)
                and (not period_end or r.exit_time <= period_end)
            ]
        
        # Compute stats
        total_trades = len(reflections)
        win_count = sum(1 for r in reflections if r.outcome == TradeOutcome.WIN)
        loss_count = sum(1 for r in reflections if r.outcome == TradeOutcome.LOSS)
        breakeven_count = sum(1 for r in reflections if r.outcome == TradeOutcome.BREAKEVEN)
        
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0.0
        
        total_pl = sum(r.realized_pl for r in reflections)
        
        wins = [r for r in reflections if r.outcome == TradeOutcome.WIN]
        losses = [r for r in reflections if r.outcome == TradeOutcome.LOSS]
        
        avg_win = (sum(r.realized_pl for r in wins) / len(wins)) if wins else 0.0
        avg_loss = (sum(r.realized_pl for r in losses) / len(losses)) if losses else 0.0
        
        largest_win = max((r.realized_pl for r in wins), default=0.0)
        largest_loss = min((r.realized_pl for r in losses), default=0.0)
        
        avg_rr_actual = sum(r.rr_actual for r in reflections) / total_trades
        avg_rr_planned = sum(r.rr_planned for r in reflections) / total_trades
        avg_efficiency = sum(r.efficiency for r in reflections) / total_trades
        avg_duration_seconds = sum(r.duration_seconds for r in reflections) / total_trades
        
        # Strategy breakdown
        strategy_breakdown = self._compute_strategy_breakdown(reflections)
        
        # Regime breakdown
        regime_breakdown = self._compute_regime_breakdown(reflections)
        
        return PerformanceMetrics(
            total_trades=total_trades,
            win_count=win_count,
            loss_count=loss_count,
            breakeven_count=breakeven_count,
            win_rate=win_rate,
            total_pl=total_pl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            avg_rr_actual=avg_rr_actual,
            avg_rr_planned=avg_rr_planned,
            avg_efficiency=avg_efficiency,
            avg_duration_seconds=avg_duration_seconds,
            strategy_breakdown=strategy_breakdown,
            regime_breakdown=regime_breakdown,
            period_start=period_start or reflections[0].entry_time,
            period_end=period_end or reflections[-1].exit_time
        )
    
    def _compute_strategy_breakdown(self, reflections: List[TradeReflection]) -> Dict[str, Dict[str, Any]]:
        """Compute per-strategy metrics."""
        by_strategy = defaultdict(list)
        for r in reflections:
            by_strategy[r.strategy].append(r)
        
        breakdown = {}
        for strategy, refs in by_strategy.items():
            total = len(refs)
            wins = sum(1 for r in refs if r.outcome == TradeOutcome.WIN)
            breakdown[strategy] = {
                "total": total,
                "wins": wins,
                "losses": total - wins,
                "win_rate": (wins / total * 100) if total > 0 else 0.0,
                "total_pl": sum(r.realized_pl for r in refs),
                "avg_rr": sum(r.rr_actual for r in refs) / total if total > 0 else 0.0
            }
        
        return breakdown
    
    def _compute_regime_breakdown(self, reflections: List[TradeReflection]) -> Dict[str, Dict[str, Any]]:
        """Compute per-regime metrics."""
        by_regime = defaultdict(list)
        for r in reflections:
            by_regime[r.entry_regime].append(r)
        
        breakdown = {}
        for regime, refs in by_regime.items():
            total = len(refs)
            wins = sum(1 for r in refs if r.outcome == TradeOutcome.WIN)
            breakdown[regime] = {
                "total": total,
                "wins": wins,
                "losses": total - wins,
                "win_rate": (wins / total * 100) if total > 0 else 0.0,
                "total_pl": sum(r.realized_pl for r in refs),
                "avg_efficiency": sum(r.efficiency for r in refs) / total if total > 0 else 0.0
            }
        
        return breakdown
    
    def get_reflections(self, symbol: Optional[str] = None, strategy: Optional[str] = None) -> List[TradeReflection]:
        """Get reflections filtered by symbol/strategy."""
        reflections = self._reflections
        if symbol:
            reflections = [r for r in reflections if r.symbol == symbol]
        if strategy:
            reflections = [r for r in reflections if r.strategy == strategy]
        return reflections


# Global instance
_global_learning: Optional[LearningEngine] = None


def get_learning_engine() -> LearningEngine:
    global _global_learning
    if _global_learning is None:
        _global_learning = LearningEngine()
    return _global_learning