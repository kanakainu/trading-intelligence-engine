"""Relationship validator for TIE Knowledge Graph."""
import logging
from typing import Dict, Set, Tuple, List
from core.relationships.relationship import Relationship
from core.relationships.relationship_types import RelationshipType

log = logging.getLogger(__name__)


class RelationshipValidator:
    def __init__(self, known_ids: Set[str]):
        self.known_ids = known_ids
        self._registered: Set[Tuple[str, str, str]] = set()  # (src, tgt, type)

    def validate(self, rel: Relationship) -> Tuple[bool, str]:
        # 1. Source must exist
        if rel.source_id not in self.known_ids:
            return False, f"source_id not found: {rel.source_id}"

        # 2. Target must exist
        if rel.target_id not in self.known_ids:
            return False, f"target_id not found: {rel.target_id}"

        # 3. Relationship type valid
        try:
            RelationshipType(rel.relationship_type)
        except ValueError:
            return False, f"invalid relationship_type: {rel.relationship_type}"

        # 4. Duplicate check
        key = (rel.source_id, rel.target_id, str(rel.relationship_type))
        if key in self._registered:
            return False, f"duplicate relationship: {key}"

        # 5. Simple circular dependency check (direct A->B and B->A of same type)
        reverse_key = (rel.target_id, rel.source_id, str(rel.relationship_type))
        if reverse_key in self._registered:
            return False, f"circular dependency: {rel.source_id} <-> {rel.target_id} [{rel.relationship_type}]"

        self._registered.add(key)
        return True, "Valid"

    def validate_all(self, relationships: List[Relationship]) -> List[Tuple[Relationship, bool, str]]:
        return [(r, *self.validate(r)) for r in relationships]
