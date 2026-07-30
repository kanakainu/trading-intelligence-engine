"""Knowledge Validator — orchestrates all validators over a Knowledge Pack."""
import os, yaml, logging
from typing import Dict, List, Set
from core.validator.dependency_validator import DependencyValidator
from core.validator.relationship_validator import RelationshipValidator
from core.validator.integrity_validator import IntegrityValidator
from core.validator.validation_report import ValidationReport

log = logging.getLogger(__name__)

BYSTRA_PACKS = {
    "Concept":       "knowledge/bystra/concepts",
    "Structure":     "knowledge/bystra/structures",
    "Location":      "knowledge/bystra/locations",
    "Confirmation":  "knowledge/bystra/confirmations",
    "Risk":          "knowledge/bystra/risks",
    "Entry Pattern": "knowledge/bystra/entry_patterns",
    "Setup":         "knowledge/bystra/setups",
}


def _load_dir(base: str, rel_path: str) -> List[Dict]:
    path = os.path.join(base, rel_path)
    if not os.path.isdir(path):
        return []
    return [yaml.safe_load(open(os.path.join(path, f)))
            for f in os.listdir(path) if f.endswith(".yaml")]


def validate_bystra(base_path: str) -> ValidationReport:
    report = ValidationReport()
    all_objects: List[Dict] = []

    for label, rel in BYSTRA_PACKS.items():
        objs = _load_dir(base_path, rel)
        report.counts[label] = len(objs)
        all_objects.extend(objs)

    all_ids: Set[str] = {o.get("id", "") for o in all_objects}

    # 1. Duplicates
    iv = IntegrityValidator()
    dup_errs = iv.check_duplicates(all_objects)
    report.errors.extend(dup_errs)

    # 2. Missing references
    dv = DependencyValidator(all_ids)
    for obj in all_objects:
        report.errors.extend(dv.check(obj))

    # 3. Circular deps — only on 'requires' (actual dependency, not mutual refs)
    graph: Dict[str, List[str]] = {}
    for obj in all_objects:
        oid = obj.get("id", "")
        deps = [ref for ref in obj.get("requires", [])
                if isinstance(ref, str) and ref.startswith("BYS-")]
        if deps:
            graph[oid] = deps
    rv = RelationshipValidator()
    report.errors.extend(rv.check_circular(graph))

    # 4. Orphan check — find IDs referenced by setups
    referenced: Set[str] = set()
    for obj in all_objects:
        for field in ["requires", "related_objects", "strengthens",
                      "required_structures", "required_concepts", "invalid_if"]:
            for ref in obj.get(field, []):
                if isinstance(ref, str) and ref.startswith("BYS-"):
                    referenced.add(ref)
    orphan_warnings = iv.check_orphans(all_ids, referenced)
    report.warnings.extend(orphan_warnings)

    return report


if __name__ == "__main__":
    import sys
    base = sys.argv[1] if len(sys.argv) > 1 else "."
    r = validate_bystra(base)
    print(r.print())
