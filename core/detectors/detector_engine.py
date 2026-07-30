"""Detector Engine — orchestrates detector execution, aggregates Facts."""
import logging
from typing import Dict, List, Any
from core.detectors.detector_interface import DetectorInterface
from core.detectors.detector_registry import DetectorRegistry
from core.detectors.fact import Fact
from core.context.context_model import MarketContext

log = logging.getLogger(__name__)


class DetectorEngine:
    def __init__(self, registry: DetectorRegistry):
        self.registry = registry

    def run(self, context: MarketContext) -> List[Fact]:
        ids = self.registry.list()
        log.info(f"Loaded {len(ids)} Detectors: {ids}")
        all_facts: List[Fact] = []

        for detector_id in ids:
            detector = self.registry.get(detector_id)
            try:
                log.info(f"Executing {detector_id}")
                if not detector.health_check():
                    log.warning(f"Detector unhealthy, skipping: {detector_id}")
                    continue
                facts = detector.detect(context)
                for f in facts:
                    log.info(f"Fact Created: {f}")
                all_facts.extend(facts)
                log.info(f"Detector Completed: {detector_id} → {len(facts)} fact(s)")
            except Exception as e:
                log.error(f"Detector failure [{detector_id}]: {e}")

        return all_facts
