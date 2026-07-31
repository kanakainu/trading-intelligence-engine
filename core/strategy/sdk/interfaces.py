"""SDK — DetectorBase, FilterBase, ExitBase interfaces + result models."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── Detector ──────────────────────────────────────────────────────────────────

@dataclass
class DetectorResult:
    id: str
    name: str
    confidence: float
    direction: str          # BUY | SELL | NEUTRAL
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class DetectorBase(ABC):
    @property
    @abstractmethod
    def id(self) -> str: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def detect(self, context: Any) -> Optional[DetectorResult]: ...


# ── Filter ────────────────────────────────────────────────────────────────────

@dataclass
class FilterResult:
    approved: bool
    reject_reason: Optional[str] = None
    risk_score: float = 0.0


class FilterBase(ABC):
    @property
    @abstractmethod
    def id(self) -> str: ...

    @abstractmethod
    def evaluate(self, context: Any, detector_result: DetectorResult) -> FilterResult: ...


# ── Exit ──────────────────────────────────────────────────────────────────────

@dataclass
class ExitResult:
    should_close: bool
    close_reason: Optional[str] = None
    priority: int = 0       # higher = more urgent


class ExitBase(ABC):
    @property
    @abstractmethod
    def id(self) -> str: ...

    @abstractmethod
    def evaluate(self, context: Any, position: Any) -> ExitResult: ...
