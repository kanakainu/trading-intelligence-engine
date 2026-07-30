"""Relationship types for TIE Knowledge Graph."""
from enum import Enum


class RelationshipType(str, Enum):
    USED_BY = "used_by"
    REQUIRES = "requires"
    DEPENDS_ON = "depends_on"
    CONFLICTS_WITH = "conflicts_with"
    INVALIDATES = "invalidates"
    EXTENDS = "extends"
    PARENT_OF = "parent_of"
    CHILD_OF = "child_of"
