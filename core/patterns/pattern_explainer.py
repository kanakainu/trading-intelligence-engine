"""PatternExplainer — human-readable explanation of pattern match result."""
from typing import List


def build_explanation(
    pattern_name: str,
    matched: List[str],
    failed: List[str],
    score: float,
) -> str:
    lines = [f"Pattern: {pattern_name}  score={score:.0%}"]
    for m in matched: lines.append(f"  ✓ {m}")
    for f in failed:  lines.append(f"  ✗ {f} (missing)")
    return "\n".join(lines)
