"""MarkdownRenderer — ExplanationReport → Markdown string."""
from core.explanation.explanation_report import ExplanationReport


def render_markdown(report: ExplanationReport) -> str:
    lines = ["# TIE Explanation Report", ""]
    lines.append(f"**Decision:** `{report.decision.get('action','?')}`  ")
    lines.append(f"**Setup:** {report.decision.get('setup_name','')}  ")
    lines.append(f"**Confidence:** {report.decision.get('confidence',0):.0%}  ")
    lines.append(f"**Reason:** {report.decision.get('reason','')}  ")
    lines.append(f"**Timestamp:** {report.timestamp.isoformat()}")
    lines.append("")
    lines.append("## Facts")
    for f in report.facts:
        n = f.get("name","?") if isinstance(f, dict) else getattr(f,"name","?")
        v = f.get("value","?") if isinstance(f, dict) else getattr(f,"value","?")
        lines.append(f"- `{n}` = `{v}`")
    lines.append("")
    lines.append("## Trace")
    for line in report.trace_tree:
        lines.append(line)
    return "\n".join(lines)
