"""Fact Validator — duplicate, invalid, expired checks."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Tuple
from core.detectors.fact import Fact

log = logging.getLogger(__name__)
MAX_AGE_SECONDS = 300  # facts older than 5 min = expired


class FactValidator:
    def validate_all(self, facts: List[Fact]) -> Tuple[List[Fact], List[str]]:
        seen = set()
        valid, issues = [], []
        for f in facts:
            key = (f.detector_id, f.fact_type, str(f.value))
            if key in seen:
                issues.append(f"Duplicate: {key}")
                continue
            if not f.fact_type or f.value is None:
                issues.append(f"Invalid fact from {f.detector_id}: missing type or value")
                continue
            age = (datetime.now(timezone.utc) - f.timestamp).total_seconds()
            if age > MAX_AGE_SECONDS:
                issues.append(f"Expired fact from {f.detector_id}: age={age:.0f}s")
                continue
            seen.add(key)
            valid.append(f)
        return valid, issues
