"""Integrity Validator — duplicate IDs, invalid categories, orphan objects."""
from typing import Any, Dict, List, Set


VALID_CATEGORIES = {
    "Concept", "Structure", "Location", "Confirmation", "Risk", "Setup",
    "Entry Pattern", "Market Condition", "Liquidity", "Trend", "Session",
    "Timeframe", "Exit",
}


class IntegrityValidator:
    def check_duplicates(self, objects: List[Dict]) -> List[str]:
        seen_ids, seen_names = {}, {}
        errs = []
        for obj in objects:
            oid = obj.get("id", "")
            name = obj.get("name", "")
            if oid in seen_ids:
                errs.append(f"DUPLICATE_ID:{oid}")
            else:
                seen_ids[oid] = True
            if name and name in seen_names:
                errs.append(f"DUPLICATE_NAME:{name}")
            else:
                seen_names[name] = True
        return errs

    def check_orphans(self, all_ids: Set[str], referenced_ids: Set[str]) -> List[str]:
        orphans = all_ids - referenced_ids
        return [f"ORPHAN:{oid}" for oid in sorted(orphans)]
