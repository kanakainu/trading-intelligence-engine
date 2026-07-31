"""Learning Engine Package — Post-trade reflection and analytics.

Usage:
    from core.learning import get_learning_engine, TradeOutcome, ExitReason
    from datetime import datetime
    
    le = get_learning_engine()
    reflection = le.reflect(
        trade_id="t123",
        symbol="XAUUSD",
        strategy="Bystra",
        outcome=TradeOutcome.WIN,
        exit_reason=ExitReason.TP_HIT,
        realized_pl=50.0,
        risk_amount=25.0,
        rr_planned=2.0,
        duration_seconds=3600,
        entry_time=datetime.now(),
        exit_time=datetime.now(),
        entry_regime="TRENDING",
        entry_confidence=0.78,
        opportunity_priority=6,
        exit_regime="TRENDING",
        exit_price=2055.0,
        entry_price=2041.0,
        sl_price=2035.0,
        tp_price=2055.0,
        max_favorable_excursion=60.0,
        max_adverse_excursion=10.0,
        entry_features={"atr": 5.0, "ema21": 2040.0}
    )
    
    metrics = le.compute_metrics()
    print(metrics.win_rate, metrics.total_pl)
"""
from core.learning.learning_models import (
    TradeReflection,
    PerformanceMetrics,
    TradeOutcome,
    ExitReason,
)
from core.learning.learning_engine import (
    LearningEngine,
    get_learning_engine,
)

__all__ = [
    "TradeReflection",
    "PerformanceMetrics",
    "TradeOutcome",
    "ExitReason",
    "LearningEngine",
    "get_learning_engine",
]

__version__ = "1.0.0"