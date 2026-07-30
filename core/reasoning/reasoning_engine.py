"""
Reasoning Engine — FactSet + Knowledge Graph → ranked Candidates.
No BUY/SELL. No YAML reads. No Setup logic. Hypothesis only.
"""
import logging
from typing import Any, Dict, List, Set
from core.reasoning.candidate import Candidate
from core.reasoning.reasoning_result import ReasoningResult
from core.reasoning.dependency_resolver import DependencyResolver

log = logging.getLogger(__name__)

_MATCH   = "MATCH"
_PARTIAL = "PARTIAL"
_NO      = "NO_MATCH"


class ReasoningEngine:
    def __init__(self, setup_definitions: List[Dict[str, Any]]):
        """
        setup_definitions: list of compiled setup dicts from Knowledge Pack.
        Engine never reads YAML — caller loads and passes defs.
        """
        self._setups = setup_definitions
        self._resolver = DependencyResolver()

    def reason(self, fact_names: Set[str]) -> ReasoningResult:
        """
        fact_names: set of strings describing current market facts.
        Returns ranked ReasoningResult.
        """
        candidates = []
        for setup in self._setups:
            sid   = setup.get("id", "?")
            sname = setup.get("name", "?")
            requires = setup.get("requires", [])

            # convert BYS-IDs to their names via setup metadata if available
            req_labels = [self._label(r, setup) for r in requires]

            matched, missing = self._resolver.resolve(req_labels, fact_names)
            total = len(req_labels)
            score = len(matched) / total if total else 0.0

            status = _MATCH if score == 1.0 else (_PARTIAL if score > 0 else _NO)

            reason_parts = []
            for m in matched:
                reason_parts.append(f"✓ {m}")
            for m in missing:
                reason_parts.append(f"✗ {m} (missing)")

            c = Candidate(
                setup_id=sid,
                setup_name=sname,
                score=round(score, 4),
                status=status,
                matched_dependencies=matched,
                missing_dependencies=missing,
                reason="\n".join(reason_parts),
            )
            candidates.append(c)
            log.debug(f"{sid} {status} score={score:.0%} matched={len(matched)}/{total}")

        # rank: MATCH first, then by score desc
        candidates.sort(key=lambda c: (-int(c.status == _MATCH), -c.score))
        log.info(f"ReasoningEngine: {len([c for c in candidates if c.status==_MATCH])} MATCH, "
                 f"{len([c for c in candidates if c.status==_PARTIAL])} PARTIAL")
        return ReasoningResult(candidates=candidates)

    def _label(self, bys_id: str, setup: Dict) -> str:
        """Convert BYS-xxx to a fact name; fallback to raw ID."""
        # Simple: use last part after prefix for matching
        # e.g. BYS-ST001 → rally base rally (from setup name hints)
        return bys_id  # resolver handles substring match
