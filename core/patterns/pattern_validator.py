"""PatternValidator — check PatternDefinition integrity before use."""
from typing import List, Tuple
from core.patterns.pattern_definition import PatternDefinition


class PatternValidator:
    def validate(self, pattern: PatternDefinition) -> Tuple[bool, List[str]]:
        errors = []
        if not pattern.id:        errors.append("missing:id")
        if not pattern.name:      errors.append("missing:name")
        if not pattern.required_rules:
            errors.append("required_rules:empty")
        return len(errors) == 0, errors
