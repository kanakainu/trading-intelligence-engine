"""DecisionExplainer — human-readable explanation for TradeDecision."""
from typing import List
from core.setup.setup_match import SetupMatch


def build_explanation(
    action: str,
    best: SetupMatch,
    reason: str,
    all_candidates: List[SetupMatch],
) -> str:
    lines = [
        f"Decision: {action}",
        f"Setup: {best.setup_name} (conf={best.confidence:.0%})",
        f"Reason: {reason}",
        "",
        "Matched:",
    ]
    for m in best.matched_dependencies: lines.append(f"  ✓ {m}")
    if best.missing_dependencies:
        lines.append("Missing:")
        for m in best.missing_dependencies: lines.append(f"  ✗ {m}")
    return "\n".join(lines)
