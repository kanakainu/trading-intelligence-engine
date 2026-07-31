"""Trade Planner Package — SL/TP/DZ/RR calculator.

Usage:
    from core.planner import build_trade_plan, PlannerInputs
    
    inputs = PlannerInputs(
        symbol="XAUUSD",
        direction="buy",
        entry_zone={"low": 2040, "high": 2042},
        confidence=0.78,
        strategies=["SNRC1", "Hybrid1"],
        timeframe="M5",
        h1_support=2030,
        h1_resistance=2055,
        candles={"M5": [...], "H1": [...]},
        spread_buffer=0.5,
        atr=5.0,
        balance=1000,
        risk_per_trade_pct=1.0,
        scan_id="scan_123"
    )
    
    plan = build_trade_plan(inputs)
    print(plan.to_dict())
"""
from core.planner.planner_models import (
    TradePlan,
    PlannerInputs,
)
from core.planner.trade_planner import (
    TradePlanner,
    get_trade_planner,
    build_trade_plan,
)

__all__ = [
    "TradePlan",
    "PlannerInputs",
    "TradePlanner",
    "get_trade_planner",
    "build_trade_plan",
]

__version__ = "1.0.0"