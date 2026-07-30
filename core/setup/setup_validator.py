"""Setup Validator — validate setup definitions before evaluation."""
from typing import Any, Dict, List, Tuple

VALID_OPS = {"AND", "OR", "NOT", "eq", "neq"}
REQUIRED_FIELDS = {"id", "name", "rules"}


class SetupValidator:
    def validate(self, setup_def: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        for f in REQUIRED_FIELDS:
            if f not in setup_def:
                errors.append(f"missing_field:{f}")
        if "rules" in setup_def:
            self._validate_rule(setup_def["rules"], errors)
        return len(errors) == 0, errors

    def _validate_rule(self, rule: Dict, errors: List[str]) -> None:
        op = rule.get("op", "").upper()
        if "fact" in rule:
            if rule.get("op", "eq").lower() not in VALID_OPS:
                errors.append(f"invalid_op:{rule.get('op')}")
            return
        if op not in {"AND", "OR", "NOT"}:
            errors.append(f"invalid_compound_op:{op}")
        for child in rule.get("rules", []):
            self._validate_rule(child, errors)
