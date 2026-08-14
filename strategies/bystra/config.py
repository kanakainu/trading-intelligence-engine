"""Bystra Strategy — runtime config."""
from dataclasses import dataclass, field
from typing import List


@dataclass
class BystraConfig:
    min_confidence: float = 0.75
    enabled_detectors: List[str] = field(default_factory=lambda: [
        "THREE_CANDLE",  # CAPYBARS big-small-big compression — ONLY ONE
    ])
    max_signals_per_scan: int = 1
    require_htf_confirm: bool = True
    # Price-zone cooldown: zone radius in price points.
    # Pattern at same price zone blocked until price moves beyond radius.
    # THREE_CANDLE exempt (fresh pattern each candle).
    zone_cooldown_exempt: List[str] = field(default_factory=lambda: ["THREE_CANDLE"])
    zone_radius_pts: float = 3.0  # XAUUSD: ~3 pts = 30 pips
