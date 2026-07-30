"""Setup Engine — evaluate FactSet against KnowledgeObject setup defs."""
import logging
from typing import List
from core.detectors.fact import Fact
from core.facts.factset import FactSet
from core.setup.rule_evaluator import evaluate_rule, _build_index
from core.setup.setup_registry import SetupRegistry
from core.setup.setup_result import SetupResult, SetupStatus

log = logging.getLogger(__name__)


class SetupEngine:
    """
    Receives compiled KnowledgeObjects (via SetupRegistry).
    Never reads YAML directly — that is the KnowledgeLoader's job.
    """

    def __init__(self, registry: SetupRegistry):
        self.registry = registry

    def evaluate(self, factset: FactSet) -> List[SetupResult]:
        ids = self.registry.list()
        log.info(f"Loaded {len(ids)} Setup Definitions")
        fact_index = _build_index(factset.facts)
        results = []

        for sid in ids:
            setup_def = self.registry.get(sid)
            log.info(f"Evaluating Setup {sid}")
            rule = setup_def.get("rules", {})
            ok, _, matched, failed = evaluate_rule(rule, fact_index)
            missing = [f.replace("missing:", "") for f in failed if f.startswith("missing:")]
            score = len(matched) / max(len(matched) + len(failed), 1)
            confidence = float(setup_def.get("confidence", 0.7)) * score
            status = SetupStatus.PASS if ok else SetupStatus.FAIL

            result = SetupResult(
                setup_id=sid,
                status=status,
                score=round(score, 4),
                confidence=round(confidence, 4),
                matched_rules=matched,
                failed_rules=failed,
                missing_facts=missing,
            )
            log.info(f"Matched Rules: {len(matched)} | Failed: {len(failed)} | Setup Result: {status}")
            results.append(result)

        return results
