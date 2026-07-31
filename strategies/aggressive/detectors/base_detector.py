"""Base Detector for aggressive strategy."""
from abc import ABC, abstractmethod
from typing import Optional

from core.features.feature_models import FeatureSnapshot
from strategies.aggressive.regime.regime_snapshot import AggressiveRegimeSnapshot
from strategies.aggressive.detectors.detector_result import DetectorResult


class BaseDetector(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def detect(
        self,
        features: FeatureSnapshot,
        regime: AggressiveRegimeSnapshot,
    ) -> Optional[DetectorResult]:
        """Return DetectorResult or None."""
        ...
