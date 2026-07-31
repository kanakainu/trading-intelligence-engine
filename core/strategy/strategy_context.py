"""Strategy Context — inputs for strategy execution."""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from core.context.scan_context import ScanContext
from core.lifecycle.lifecycle_models import PositionSnapshot


@dataclass(frozen=True, slots=True)
class StrategyContext:
    """Complete context passed to strategy."""
    # Market scan
    scan: ScanContext
    
    # Active positions (if any)
    position: Optional[PositionSnapshot] = None
    
    # Timing
    timestamp: datetime = datetime.now()
