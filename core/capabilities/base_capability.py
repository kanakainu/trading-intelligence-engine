"""Abstract base class for all capabilities."""

from abc import ABC
from core.features.feature_models import FeatureSnapshot


class BaseCapability(ABC):
    """Base capability — consumes FeatureSnapshot, exposes interpreted properties.
    
    No strategy logic. Pure interpretation of features.
    """
    
    def __init__(self, feature_snapshot: FeatureSnapshot):
        self._fs = feature_snapshot
    
    @property
    def feature_snapshot(self) -> FeatureSnapshot:
        return self._fs
    
    @property
    def symbol(self) -> str:
        return self._fs.symbol
    
    @property
    def timestamp(self):
        return self._fs.timestamp
    
    @property
    def scan_id(self) -> str:
        return self._fs.scan_id
