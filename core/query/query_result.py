"""QueryResult — generic output of all Knowledge Query Engine calls."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class QueryResult:
    success: bool = False
    object: Optional[Dict[str, Any]] = None
    related_objects: List[Dict] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    message: str = ""

    def __repr__(self):
        return f"<QueryResult success={self.success} obj={self.object.get('id') if self.object else None}>"
