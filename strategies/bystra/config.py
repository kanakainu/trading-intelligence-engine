"""Bystra Strategy — runtime config."""
from dataclasses import dataclass, field
from typing import List


@dataclass
class BystraConfig:
    min_confidence: float = 0.75
    enabled_detectors: List[str] = field(default_factory=lambda: [
        "SNRC1", "SNRC2", "SNRC3",
        "HYBRID1", "HYBRID2",
        "MANIPULATION",
        "QMR", "QMC", "QMM", "QM2P",
        "BLINDSPOT", "BLINDSPOT2",
        "CLAB", "MOTHER_CANDLE",
    ])
    max_signals_per_scan: int = 1
    require_htf_confirm: bool = True
