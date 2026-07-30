"""Explanation Validator — checks for broken references."""
from typing import List, Tuple
from core.explanation.explanation_report import ExplanationReport
from core.facts.factset import FactSet
from core.setup.setup_result import SetupResult
from core.decision.decision import Decision


class ExplanationValidator:
    def validate(self, report: ExplanationReport,
                 factset: FactSet, result: SetupResult, decision: Decision) -> Tuple[bool, List[str]]:
        errors = []

        if report.decision_id != decision.decision_id:
            errors.append(f"broken_ref:decision_id {report.decision_id} != {decision.decision_id}")
        if report.setup_id != result.setup_id:
            errors.append(f"broken_ref:setup_id {report.setup_id} != {result.setup_id}")

        fact_types = {f.fact_type for f in factset.facts}
        for mf in report.matched_facts:
            if mf.get("fact_type") not in fact_types:
                errors.append(f"broken_ref:fact_type {mf.get('fact_type')}")

        return len(errors) == 0, errors
