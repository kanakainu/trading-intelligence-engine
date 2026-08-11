"""Bystra Strategy — runtime config."""
from dataclasses import dataclass, field
from typing import List


@dataclass
class BystraConfig:
    min_confidence: float = 0.75
    enabled_detectors: List[str] = field(default_factory=lambda: [
    "SNRC1", "SNRC2", "SNRC3",
    "HYBRID1", "HYBRID2",
    # "MANIPULATION",  # rare — fake breakout, disabled
    "QMR", "QMC", "QMM", "QM2P",
    # "BLINDSPOT", "BLINDSPOT2",  # rare — hidden zone, disabled
    # "CLAB",  # confirmation only, disabled
    # "MOTHER_CANDLE",  # too selective, disabled
    "THREE_CANDLE",  # CAPYBARS-style big-small-big compression
    ])
    max_signals_per_scan: int = 1
    require_htf_confirm: bool = True
