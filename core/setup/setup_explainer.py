"""SetupExplainer — human-readable path for setup resolution."""
from typing import List


def build_explanation(
    setup_name: str,
    status: str,
    matched: List[str],
    missing: List[str],
    confidence: float,
) -> str:
    lines = [f"Setup: {setup_name}  status={status}  confidence={confidence:.0%}"]
    for m in matched: lines.append(f"  ✓ {m}")
    for m in missing: lines.append(f"  ✗ {m} (missing)")
    return "\n".join(lines)
