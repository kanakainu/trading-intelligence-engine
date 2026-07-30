"""DecisionRanker — sort SetupMatch candidates for Decision Pipeline."""
from typing import Any, Dict, List
from core.setup.setup_match import SetupMatch, READY


def rank_candidates(
    candidates: List[SetupMatch],
    setup_priority: Dict[str, int],
) -> List[SetupMatch]:
    def key(m: SetupMatch):
        prio = setup_priority.get(m.setup_id, 999)
        return (-int(m.status == READY), prio, -m.confidence)
    return sorted(candidates, key=key)
