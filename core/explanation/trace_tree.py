"""TraceTree — builds step-by-step reasoning chain from engine outputs."""
from typing import Any, Dict, List


def build_trace_tree(
    facts: List[Any],
    rule_results: List[Dict],
    patterns: List[Any],
    setups: List[Any],
    decision: Any,
) -> List[str]:
    lines = ["=== TRACE TREE ===", ""]

    lines.append("[ FACTS ]")
    for f in facts:
        if hasattr(f, "name"):
            lines.append(f"  {f.type:<24} {f.name} = {f.value}")
        elif isinstance(f, dict):
            lines.append(f"  {f.get('type','?'):<24} {f.get('name','?')} = {f.get('value','?')}")
    lines.append("")

    if rule_results:
        lines.append("[ RULES ]")
        for rr in rule_results:
            label = rr.get("label","?")
            passed = rr.get("passed", False)
            lines.append(f"  {'✓' if passed else '✗'} {label}")
        lines.append("")

    if patterns:
        lines.append("[ PATTERNS ]")
        for p in patterns:
            if hasattr(p, "status"):
                lines.append(f"  {p.status:<14} {p.pattern_name}  score={p.score:.0%}")
            elif isinstance(p, dict):
                lines.append(f"  {p.get('status','?'):<14} {p.get('pattern_name','?')}")
        lines.append("")

    if setups:
        lines.append("[ SETUPS ]")
        for s in setups:
            if hasattr(s, "status"):
                lines.append(f"  {s.status:<14} {s.setup_name}  conf={s.confidence:.0%}")
            elif isinstance(s, dict):
                lines.append(f"  {s.get('status','?'):<14} {s.get('setup_name','?')}")
        lines.append("")

    lines.append("[ DECISION ]")
    if hasattr(decision, "action"):
        lines.append(f"  Action    : {decision.action}")
        lines.append(f"  Setup     : {decision.setup_name}")
        lines.append(f"  Confidence: {decision.confidence:.0%}")
        lines.append(f"  Reason    : {decision.reason}")
    elif isinstance(decision, dict):
        lines.append(f"  Action    : {decision.get('action','?')}")
        lines.append(f"  Reason    : {decision.get('reason','?')}")

    return lines
