"""DecisionTrace — builds decision audit trail."""
from typing import Any, Dict, List
from core.setup.setup_match import SetupMatch


def build_trace(candidates: List[SetupMatch], action: str, reason: str) -> List[str]:
    lines = [f"Decision: {action}  Reason: {reason}"]
    for i, c in enumerate(candidates[:5], 1):
        lines.append(f"  #{i} {c.setup_name} [{c.status}] conf={c.confidence:.0%}")
    return lines
