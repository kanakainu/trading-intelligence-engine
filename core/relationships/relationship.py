"""Relationship object for TIE Knowledge Graph."""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from core.relationships.relationship_types import RelationshipType


@dataclass
class Relationship:
    source_id: str
    target_id: str
    relationship_type: RelationshipType
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self):
        return f"<Rel {self.source_id} --[{self.relationship_type}]--> {self.target_id}>"
