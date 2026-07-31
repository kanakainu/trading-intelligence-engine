"""Trade Lifecycle Package — Position state machine.

Usage:
    from core.lifecycle import get_trade_lifecycle, LifecycleState
    
    lc = get_trade_lifecycle()
    pos = lc.create_position(
        position_id="p123",
        symbol="XAUUSD",
        direction="buy",
        current_price=2040.0,
        volume=0.1,
        volume_remaining=0.1,
        floating_pl=0.0,
        realized_pl=0.0,
        sl=2035.0,
        tp=2055.0,
        danger_zone=2030.0,
        entry_price=None,
        opened_at=None,
        closed_at=None,
        duration_seconds=0.0
    )
    
    # Entry
    lc.update_state(
        "p123",
        LifecycleState.OPEN,
        trigger="entry",
        entry_price=2041.0,
        opened_at=datetime.now()
    )
    
    # Partial TP
    lc.update_state(
        "p123",
        LifecycleState.PARTIAL,
        trigger="partial",
        volume_remaining=0.05,
        realized_pl=50.0
    )
"""
from core.lifecycle.lifecycle_models import (
    LifecycleState,
    PositionSnapshot,
    LifecycleEvent,
)
from core.lifecycle.trade_lifecycle import (
    TradeLifecycle,
    get_trade_lifecycle,
)

__all__ = [
    "LifecycleState",
    "PositionSnapshot",
    "LifecycleEvent",
    "TradeLifecycle",
    "get_trade_lifecycle",
]

__version__ = "1.0.0"