"""Bystra Strategy — runtime config."""
from dataclasses import dataclass, field
from typing import List


@dataclass
class BystraConfig:
    min_confidence: float = 0.75
    enabled_detectors: List[str] = field(default_factory=lambda: [
        "SNRC1", "SNRC2", "SNRC3",
        "HYBRID1", "HYBRID2",
        # "MANIPULATION",  # rare — fake breakout
        "QMR", "QMC", "QMM", "QM2P",
        # "BLINDSPOT", "BLINDSPOT2",  # rare — hidden zone
        # "CLAB",  # confirmation only
        # "MOTHER_CANDLE",  # too selective
        "THREE_CANDLE",  # CAPYBARS big-small-big compression
    ])
    max_signals_per_scan: int = 1
    require_htf_confirm: bool = True
    # Price-zone cooldown: zone radius in price points.
    # Pattern at same price zone blocked until price moves beyond radius.
    # THREE_CANDLE exempt (fresh pattern each candle).
    zone_cooldown_exempt: List[str] = field(default_factory=lambda: ["THREE_CANDLE"])
    zone_radius_pts: float = 3.0  # XAUUSD: ~3 pts = 30 pips
