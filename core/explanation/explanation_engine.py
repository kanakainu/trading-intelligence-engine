"""Explanation Engine — orchestrates builder + validator + registry."""
import logging
from typing import List
from core.facts.factset import FactSet
from core.setup.setup_result import SetupResult
from core.decision.decision import Decision
from core.explanation.explanation_builder import ExplanationBuilder
from core.explanation.explanation_registry import ExplanationRegistry
from core.explanation.explanation_validator import ExplanationValidator
from core.explanation.explanation_report import ExplanationReport

log = logging.getLogger(__name__)


class ExplanationEngine:
    def __init__(self):
        self.builder = ExplanationBuilder()
        self.validator = ExplanationValidator()
        self.registry = ExplanationRegistry()

    def explain(self, factset: FactSet, result: SetupResult, decision: Decision) -> ExplanationReport:
        log.info(f"Loaded Decision: {decision.decision_id}")
        log.info("Generating Explanation")

        report = self.builder.build(factset, result, decision)

        ok, errors = self.validator.validate(report, factset, result, decision)
        if not ok:
            log.warning(f"Explanation validation issues: {errors}")

        log.info(f"Matched Facts: {len(report.matched_facts)}")
        log.info(f"Matched Rules: {len(report.matched_rules)}")
        log.info(f"Failed Rules: {len(report.failed_rules)}")
        log.info("Explanation Ready")

        self.registry.register(report)
        return report
