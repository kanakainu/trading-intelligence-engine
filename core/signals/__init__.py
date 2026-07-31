"""Signal Contract Package — Standardized detector output.

Usage:
    from core.signals import Signal, Direction, SignalStatus, SignalBatch
    
    signal = Signal(
        signal_id="SNRC1_XAUUSD_20260731_143000",
        strategy="SNRC1",
        symbol="XAUUSD",
        direction=Direction.BUY,
        entry_zone={"low": 2040.0, "high": 2042.0},
        confidence=0.78,
        timeframe="M5",
        regime="TRENDING",
        opportunity_priority=6,
        metadata={"detector": "SNRC1", "base_zone": [2038, 2042]}
    )
    
    print(signal.to_dict())
"""
from core.signals.signal import (
    Signal,
    Direction,
    SignalStatus,
    SignalBatch,
)

__all__ = [
    "Signal",
    "Direction",
    "SignalStatus",
    "SignalBatch",
]

__version__ = "1.0.0"