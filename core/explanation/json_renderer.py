"""JsonRenderer — ExplanationReport → dict / JSON string."""
import json
from core.explanation.explanation_report import ExplanationReport


def _ser(obj):
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _ser(v) for k, v in vars(obj).items()}
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, (list, tuple)):
        return [_ser(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _ser(v) for k, v in obj.items()}
    return obj


def render_json(report: ExplanationReport, indent: int = 2) -> str:
    return json.dumps(_ser(report), indent=indent, ensure_ascii=False)


def render_dict(report: ExplanationReport) -> dict:
    return json.loads(render_json(report))
