"""PatternDefinition — compiled from Knowledge Pack. No YAML reads here."""
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class PatternDefinition:
    id: str
    name: str
    required_rules: List[str]          # rule labels that must PASS
    optional_rules: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
