"""ExplanationGenerator — assembles ExplanationReport from all engine outputs."""
import logging
from typing import Any, Dict, List
from core.explanation.explanation_report import ExplanationReport
from core.explanation.trace_tree import build_trace_tree

log = logging.getLogger(__name__)


class ExplanationGenerator:
    """
    Reads only engine output objects. No YAML, no candle, no broker, no MT5.
    Does NOT produce BUY/SELL. Only explains reasoning.
    """

    def generate(
        self,
        facts:        List[Any] = None,
        rule_results: List[Dict] = None,
        patterns:     List[Any] = None,
        setups:       List[Any] = None,
        decision:     Any = None,
    ) -> ExplanationReport:
        facts        = facts or []
        rule_results = rule_results or []
        patterns     = patterns or []
        setups       = setups or []

        dec_dict = {}
        if hasattr(decision, "action"):
            dec_dict = {
                "action":      decision.action,
                "setup_id":    decision.setup_id,
                "setup_name":  decision.setup_name,
                "confidence":  decision.confidence,
                "reason":      decision.reason,
            }
        elif isinstance(decision, dict):
            dec_dict = decision

        trace = build_trace_tree(facts, rule_results, patterns, setups, decision)

        # best setup name for summary
        best = next((s.setup_name for s in setups if hasattr(s,"status") and s.status=="READY"), "")
        action = dec_dict.get("action","WAIT")
        summary = f"Decision: {action}. Setup: {best}. Confidence: {dec_dict.get('confidence',0):.0%}. Reason: {dec_dict.get('reason','')}"

        facts_list = [{"type": getattr(f,"type","?"), "name": getattr(f,"name","?"),
                        "value": str(getattr(f,"value","?"))} if not isinstance(f, dict) else f
                      for f in facts]

        report = ExplanationReport(
            facts=facts_list,
            rule_results=rule_results,
            patterns=[vars(p) if hasattr(p,"__dataclass_fields__") else p for p in patterns],
            setups=[vars(s) if hasattr(s,"__dataclass_fields__") else s for s in setups],
            decision=dec_dict,
            trace_tree=trace,
            summary=summary,
        )
        log.info(f"ExplanationGenerator: {action} conf={dec_dict.get('confidence',0):.0%} facts={len(facts)}")
        return report
