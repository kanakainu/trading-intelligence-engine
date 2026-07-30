"""SetupMatch — output of SetupResolver for one setup candidate."""
from dataclasses import dataclass, field
from typing import Any, Dict, List

READY      = "READY"
PARTIAL    = "PARTIAL"
NOT_READY  = "NOT_READY"


@dataclass
class SetupMatch:
    setup_id: str
    setup_name: str
    status: str                        # READY | PARTIAL | NOT_READY
    confidence: float                  # 0.0–1.0
    matched_dependencies: List[str]  = field(default_factory=list)
    missing_dependencies: List[str]  = field(default_factory=list)
    waiting_for: List[str]           = field(default_factory=list)
    reasoning_path: List[str]        = field(default_factory=list)
    explanation: str = ""

    def __repr__(self):
        return f"<SetupMatch {self.setup_id} {self.status} conf={self.confidence:.0%}>"
