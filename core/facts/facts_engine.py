"""Facts Engine — aggregate, validate, resolve → FactSet."""
import logging
from datetime import datetime, timezone
from typing import List
from core.detectors.fact import Fact
from core.facts.factset import FactSet
from core.facts.fact_registry import FactRegistry
from core.facts.fact_validator import FactValidator
from core.facts.fact_resolver import FactResolver

log = logging.getLogger(__name__)


class FactsEngine:
    def __init__(self):
        self.registry = FactRegistry()
        self.validator = FactValidator()
        self.resolver = FactResolver()

    def process(self, facts: List[Fact], market: str = "", timeframe: str = "") -> FactSet:
        log.info(f"Loaded {len(facts)} Facts")

        for f in facts:
            self.registry.add(f)

        valid, issues = self.validator.validate_all(self.registry.list())
        removed = len(self.registry) - len(valid)
        if removed:
            log.info(f"{removed} Duplicate/Invalid/Expired Removed")

        resolved_facts, conflicts = self.resolver.resolve(valid)
        if conflicts:
            log.info(f"{len(conflicts)} Conflict Found")

        factset = FactSet(
            timestamp=datetime.now(timezone.utc),
            market=market,
            timeframe=timeframe,
            facts=resolved_facts,
            conflicts=conflicts,
        )
        log.info(f"FactSet Generated: {factset}")
        return factset
