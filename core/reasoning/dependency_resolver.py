"""Dependency Resolver — match FactSet against Setup requires list."""
from typing import Any, Dict, List, Set, Tuple


class DependencyResolver:
    def resolve(self, requires: List[str], fact_names: Set[str]) -> Tuple[List[str], List[str]]:
        """
        Returns (matched, missing).
        Match strategy:
          1. Direct ID match (BYS-xxx in facts)
          2. Keyword match — normalize both sides, check substring
        """
        matched, missing = [], []
        for req in requires:
            if self._match(req, fact_names):
                matched.append(req)
            else:
                missing.append(req)
        return matched, missing

    def _match(self, req: str, fact_names: Set[str]) -> bool:
        req_lower = req.lower().replace("-", " ").replace("_", " ")
        for name in fact_names:
            n = name.lower().replace("-", " ").replace("_", " ")
            if req_lower == n or req_lower in n or n in req_lower:
                return True
        return False
