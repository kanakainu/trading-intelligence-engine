"""
SetupResolver — translates PatternMatch + FactSet → SetupMatch[].
Reads only compiled SetupDefinition objects. No YAML, no candle, no broker.
"""
import logging
from typing import Any, Dict, List, Set
from core.setup.setup_match import SetupMatch, READY, PARTIAL, NOT_READY
from core.setup.setup_explainer import build_explanation
from core.setup.setup_ranker import rank

log = logging.getLogger(__name__)


class SetupResolver:
    def __init__(self, setup_definitions: List[Dict[str, Any]]):
        """setup_definitions: compiled dicts from KnowledgePack — no YAML read here."""
        self._setups = setup_definitions

    def resolve(
        self,
        fact_names: Set[str],
        pattern_ids: Set[str],           # matched PatternMatch pattern IDs/names
        context_facts: Dict[str, str],   # e.g. {"trend":"bullish","session":"london"}
    ) -> List[SetupMatch]:

        all_available = fact_names | pattern_ids | set(context_facts.values()) | set(context_facts.keys())
        results = []

        for sd in self._setups:
            sid   = sd.get("id","?")
            sname = sd.get("name","?")
            base_conf = float(sd.get("confidence", 0.7))

            requires = [str(r) for r in sd.get("requires", [])]
            matched, missing = self._resolve_deps(requires, all_available)
            total = len(requires)
            score = len(matched) / total if total else 1.0

            actual_conf = round(base_conf * score, 4)
            status = READY if score == 1.0 else (PARTIAL if score > 0 else NOT_READY)

            path = [f"✓ {m}" for m in matched] + [f"✗ {m}" for m in missing]
            exp = build_explanation(sname, status, matched, missing, actual_conf)

            sm = SetupMatch(
                setup_id=sid,
                setup_name=sname,
                status=status,
                confidence=actual_conf,
                matched_dependencies=matched,
                missing_dependencies=missing,
                waiting_for=missing,
                reasoning_path=path,
                explanation=exp,
            )
            results.append(sm)
            log.debug(f"{sid} {status} conf={actual_conf:.0%}")

        ranked = rank(results)
        log.info(f"SetupResolver: {len([r for r in ranked if r.status==READY])} READY, "
                 f"{len([r for r in ranked if r.status==PARTIAL])} PARTIAL")
        return ranked

    def _resolve_deps(self, requires: List[str], available: Set[str]):
        matched, missing = [], []
        for req in requires:
            if self._match(req, available):
                matched.append(req)
            else:
                missing.append(req)
        return matched, missing

    def _match(self, req: str, available: Set[str]) -> bool:
        req_l = req.lower().replace("-"," ").replace("_"," ")
        for a in available:
            a_l = str(a).lower().replace("-"," ").replace("_"," ")
            if req_l == a_l or req_l in a_l or a_l in req_l:
                return True
        return False
