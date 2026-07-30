"""Fact Resolver — detect conflicting facts, mark conflict only. No trading logic."""
import logging
from typing import Any, Dict, List, Tuple
from core.detectors.fact import Fact

log = logging.getLogger(__name__)


class FactResolver:
    def resolve(self, facts: List[Fact]) -> Tuple[List[Fact], List[Dict[str, Any]]]:
        """Group by fact_type; flag types with >1 distinct value as conflict."""
        groups: Dict[str, List[Fact]] = {}
        for f in facts:
            groups.setdefault(f.fact_type, []).append(f)

        conflicts = []
        for fact_type, group in groups.items():
            values = {str(f.value) for f in group}
            if len(values) > 1:
                conflict = {
                    "fact_type": fact_type,
                    "conflict": True,
                    "values": list(values),
                    "detectors": [f.detector_id for f in group],
                }
                conflicts.append(conflict)
                log.warning(f"Conflict [{fact_type}]: {values}")

        return facts, conflicts
