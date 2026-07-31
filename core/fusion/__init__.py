"""Signal Fusion Package — Merge multi-detector signals.

Usage:
    from core.fusion import fuse_signals, FusionInputs
    from core.signals import Signal, Direction
    from datetime import datetime
    
    signals = [
        Signal(..., strategy="SNRC1", direction=Direction.BUY, entry_zone={"low": 2040, "high": 2042}, confidence=0.78),
        Signal(..., strategy="Hybrid1", direction=Direction.BUY, entry_zone={"low": 2039, "high": 2041}, confidence=0.72),
    ]
    
    inputs = FusionInputs(signals=signals, symbol="XAUUSD", scan_id="scan_123", timestamp=datetime.now())
    fused = fuse_signals(inputs)
    
    if fused.decision.value == "conflict":
        print("REJECTED - opposing signals")
    else:
        print(f"Fused: {fused.direction}, conf={fused.confidence}, agreement={fused.agreement}")
"""
from core.fusion.fusion_models import (
    FusedSignal,
    FusionInputs,
    FusionDecision,
)
from core.fusion.fusion_engine import (
    SignalFusion,
    get_signal_fusion,
    fuse_signals,
)

__all__ = [
    "FusedSignal",
    "FusionInputs",
    "FusionDecision",
    "SignalFusion",
    "get_signal_fusion",
    "fuse_signals",
]

__version__ = "1.0.0"