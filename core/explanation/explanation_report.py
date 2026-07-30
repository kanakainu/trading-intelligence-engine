"""ExplanationReport — full audit trail. Read-only. No trading logic.
Backward-compatible with Phase 1 ExplanationEngine (decision_id, matched_facts, etc).
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ExplanationReport:
    # Phase 3 fields
    facts:        List[Dict] = field(default_factory=list)
    rule_results: List[Dict] = field(default_factory=list)
    patterns:     List[Dict] = field(default_factory=list)
    setups:       List[Dict] = field(default_factory=list)
    decision:     Dict       = field(default_factory=dict)
    trace_tree:   List[str]  = field(default_factory=list)
    summary:      str = ""
    timestamp:    datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Phase 1 backward-compat fields
    decision_id:  str = ""
    setup_id:     str = ""
    report_id:    str = field(default_factory=lambda: __import__('uuid').uuid4().hex[:8])
    matched_facts:        List[Dict] = field(default_factory=list)
    matched_rules:        List[str]  = field(default_factory=list)
    failed_rules:         List[str]  = field(default_factory=list)
    missing_facts:        List[str]  = field(default_factory=list)
    confidence_breakdown: Dict       = field(default_factory=dict)
    execution_summary:    Dict       = field(default_factory=dict)
    metadata:             Dict       = field(default_factory=dict)

    def __repr__(self):
        return f"<ExplanationReport id={self.decision_id or self.decision.get('action','?')}>"

    def to_json(self, indent: int = 2) -> str:
        from core.explanation.json_renderer import render_json
        return render_json(self)
