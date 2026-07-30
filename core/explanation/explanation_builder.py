"""Explanation Builder — structured audit trail, deterministic, no LLM."""
from typing import Any, Dict, List
from core.detectors.fact import Fact
from core.facts.factset import FactSet
from core.setup.setup_result import SetupResult
from core.decision.decision import Decision
from core.explanation.explanation_report import ExplanationReport


class ExplanationBuilder:
    def build(self, factset: FactSet, result: SetupResult, decision: Decision) -> ExplanationReport:
        matched_facts = [
            {"fact_type": f.fact_type, "value": f.value,
             "detector": f.detector_id, "confidence": f.confidence}
            for f in factset.facts
        ]

        confidence_breakdown = {
            "setup_score": result.score,
            "setup_confidence": result.confidence,
            "decision_confidence": decision.confidence,
        }

        exec_summary: Dict[str, Any] = {}
        if decision.execution_plan:
            p = decision.execution_plan
            exec_summary = {
                "entry_type": p.entry_type,
                "entry_zone": p.entry_zone,
                "stop_loss": p.stop_loss,
                "take_profit": p.take_profit,
                "risk_profile": p.risk_profile,
            }

        summary = (
            f"Setup {result.setup_id}: {result.status} "
            f"(score={result.score:.2f}, conf={result.confidence:.2f}). "
            f"Decision: {decision.action} (conf={decision.confidence:.2f}). "
            f"Reason: {decision.reason}"
        )

        return ExplanationReport(
            decision_id=decision.decision_id,
            setup_id=result.setup_id,
            summary=summary,
            matched_facts=matched_facts,
            matched_rules=result.matched_rules,
            failed_rules=result.failed_rules,
            missing_facts=result.missing_facts,
            confidence_breakdown=confidence_breakdown,
            execution_summary=exec_summary,
        )
