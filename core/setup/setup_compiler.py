"""Setup Compiler — load Setup YAML → Python object. No trading logic."""
import os, yaml, logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from core.setup.setup_schema_validator import SetupSchemaValidator

log = logging.getLogger(__name__)


@dataclass
class SetupObject:
    id: str
    name: str
    engine: str
    type: str            # LONG | SHORT | NEUTRAL
    description: str
    requires: List[str] = field(default_factory=list)
    invalid_if: List[str] = field(default_factory=list)
    priority: int = 1
    confidence: float = 0.7
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self):
        return f"<Setup {self.id} [{self.type}] engine={self.engine} conf={self.confidence}>"


class SetupCompiler:
    def __init__(self, schema_path: str):
        self.validator = SetupSchemaValidator(schema_path)

    def compile_file(self, yaml_path: str) -> Optional[SetupObject]:
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        ok, errors = self.validator.validate(data)
        if not ok:
            log.error(f"Setup validation failed [{yaml_path}]: {errors}")
            return None
        obj = SetupObject(
            id=data["id"],
            name=data["name"],
            engine=data["engine"],
            type=data["type"],
            description=data["description"],
            requires=data.get("requires", []),
            invalid_if=data.get("invalid_if", []),
            priority=int(data.get("priority", 1)),
            confidence=float(data.get("confidence", 0.7)),
            metadata=data.get("metadata", {}),
        )
        log.info(f"Compiled: {obj}")
        return obj

    def compile_dir(self, dir_path: str) -> List[SetupObject]:
        results = []
        for fname in sorted(os.listdir(dir_path)):
            if fname.endswith(".yaml"):
                obj = self.compile_file(os.path.join(dir_path, fname))
                if obj:
                    results.append(obj)
        log.info(f"Compiled {len(results)} setups from {dir_path}")
        return results
