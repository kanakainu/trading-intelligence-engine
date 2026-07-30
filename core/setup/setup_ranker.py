"""SetupRanker — rank SetupMatch list by status+confidence."""
from typing import List
from core.setup.setup_match import SetupMatch, READY, PARTIAL


def rank(matches: List[SetupMatch]) -> List[SetupMatch]:
    return sorted(
        matches,
        key=lambda m: (-int(m.status == READY), -int(m.status == PARTIAL), -m.confidence)
    )
