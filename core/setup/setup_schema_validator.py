"""Setup Schema Validator — validate Setup YAML against setup_schema. No trading logic."""
import yaml, logging
from typing import Any, Dict, List, Tuple

log = logging.getLogger(__name__)
VALID_TYPES = {"LONG", "SHORT", "NEUTRAL"}


class SetupSchemaValidator:
    REQUIRED = ["id", "name", "engine", "type", "description", "requires", "priority", "confidence"]

    def __init__(self, schema_path: str):
        with open(schema_path) as f:
            self.schema = yaml.safe_load(f)

    def validate(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        for f in self.REQUIRED:
            if f not in data:
                errors.append(f"missing_field:{f}")
        if "type" in data and data["type"] not in VALID_TYPES:
            errors.append(f"invalid_type:{data['type']}")
        if "confidence" in data:
            try:
                c = float(data["confidence"])
                if not (0.0 <= c <= 1.0):
                    errors.append(f"confidence_out_of_range:{c}")
            except (TypeError, ValueError):
                errors.append(f"confidence_not_float:{data['confidence']}")
        if "priority" in data:
            try:
                int(data["priority"])
            except (TypeError, ValueError):
                errors.append(f"priority_not_int:{data['priority']}")
        if "requires" in data and not isinstance(data["requires"], list):
            errors.append("requires_not_list")
        return len(errors) == 0, errors
