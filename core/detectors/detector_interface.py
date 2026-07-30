"""Detector Interface — all detectors must implement this. No trading logic."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from core.detectors.fact import Fact
from core.context.context_model import MarketContext


class DetectorInterface(ABC):
    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def detect(self, context: MarketContext) -> List[Fact]: ...

    @abstractmethod
    def validate(self) -> bool: ...

    @abstractmethod
    def health_check(self) -> bool: ...

    @abstractmethod
    def metadata(self) -> Dict[str, Any]: ...
