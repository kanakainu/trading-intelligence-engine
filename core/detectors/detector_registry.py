"""Detector Registry — register/lookup/list detectors."""
import logging
from typing import Dict, List, Optional
from core.detectors.detector_interface import DetectorInterface

log = logging.getLogger(__name__)


class DetectorRegistry:
    def __init__(self):
        self._store: Dict[str, DetectorInterface] = {}

    def register(self, detector_id: str, detector: DetectorInterface) -> None:
        if detector_id in self._store:
            log.warning(f"Detector already registered, overwriting: {detector_id}")
        self._store[detector_id] = detector
        log.info(f"Detector registered: {detector_id}")

    def unregister(self, detector_id: str) -> None:
        self._store.pop(detector_id, None)

    def get(self, detector_id: str) -> Optional[DetectorInterface]:
        return self._store.get(detector_id)

    def list(self) -> List[str]:
        return list(self._store.keys())

    def exists(self, detector_id: str) -> bool:
        return detector_id in self._store
