"""Dependency Validator — checks missing refs, invalid IDs, broken links."""
from typing import Any, Dict, List, Set, Tuple


class DependencyValidator:
    def __init__(self, all_ids: Set[str]):
        self.all_ids = all_ids
        self.errors: List[str] = []

    def check(self, obj: Dict[str, Any]) -> List[str]:
        errs = []
        oid = obj.get("id", "?")
        for field in ["requires", "related_objects", "used_by", "strengthens",
                      "required_structures", "required_concepts", "invalid_if"]:
            for ref in obj.get(field, []):
                if isinstance(ref, str) and ref.startswith("BYS-") and ref not in self.all_ids:
                    errs.append(f"MISSING_REF:{oid}.{field}={ref}")
        return errs
