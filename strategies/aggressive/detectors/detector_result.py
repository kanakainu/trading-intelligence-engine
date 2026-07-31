"""Detector Result — output of aggressive detectors."""
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class DetectorResult:
    direction: str          # BUY | SELL | NEUTRAL
    confidence: float       # 0-1
    strength: float         # 0-1
    reason: str
    metadata: Dict[str, Any]
