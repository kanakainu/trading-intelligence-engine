"""Typed Fact classes — Phase 3 extension. No trading logic."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict
import uuid


@dataclass
class TypedFact:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: str = ""
    name: str = ""
    value: Any = None
    confidence: float = 1.0
    source: str = ""
    timeframe: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self):
        return f"<{self.type}:{self.name}={self.value} src={self.source}>"


class TrendFact(TypedFact):
    def __init__(self, value, source="ContextEngine", **kw):
        super().__init__(type="TrendFact", name="trend", value=value, source=source, **kw)

class SessionFact(TypedFact):
    def __init__(self, value, source="ContextEngine", **kw):
        super().__init__(type="SessionFact", name="session", value=value, source=source, **kw)

class ATRFact(TypedFact):
    def __init__(self, value, source="ContextEngine", **kw):
        super().__init__(type="MarketConditionFact", name="atr", value=value, source=source, **kw)

class SpreadFact(TypedFact):
    def __init__(self, value, source="ContextEngine", **kw):
        super().__init__(type="RiskFact", name="spread", value=value, source=source, **kw)

class VolatilityFact(TypedFact):
    def __init__(self, value, source="ContextEngine", **kw):
        super().__init__(type="MarketConditionFact", name="volatility", value=value, source=source, **kw)

class MarketStatusFact(TypedFact):
    def __init__(self, value, source="ContextEngine", **kw):
        super().__init__(type="MarketConditionFact", name="market_status", value=value, source=source, **kw)

class StructureFact(TypedFact):
    def __init__(self, name, value, source="DetectorEngine", **kw):
        super().__init__(type="StructureFact", name=name, value=value, source=source, **kw)

class LocationFact(TypedFact):
    def __init__(self, name, value, source="DetectorEngine", **kw):
        super().__init__(type="LocationFact", name=name, value=value, source=source, **kw)

class ConfirmationFact(TypedFact):
    def __init__(self, name, value, source="DetectorEngine", **kw):
        super().__init__(type="ConfirmationFact", name=name, value=value, source=source, **kw)

class RiskFact(TypedFact):
    def __init__(self, name, value, source="DetectorEngine", **kw):
        super().__init__(type="RiskFact", name=name, value=value, source=source, **kw)

class LiquidityFact(TypedFact):
    def __init__(self, name, value, source="DetectorEngine", **kw):
        super().__init__(type="LiquidityFact", name=name, value=value, source=source, **kw)
