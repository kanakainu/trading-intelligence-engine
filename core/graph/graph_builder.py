"""Graph Builder — assembles KnowledgeGraph from Registry + Relationships."""
import logging
import yaml
from typing import List
from core.graph.knowledge_graph import KnowledgeGraph, Node, Edge
from core.graph.graph_validator import GraphValidator
from core.compiler.knowledge_loader import KnowledgeRegistry
from core.relationships.relationship import Relationship
from core.relationships.relationship_types import RelationshipType

log = logging.getLogger(__name__)


class GraphBuilder:
    def __init__(self, registry: KnowledgeRegistry):
        self.registry = registry
        self.graph = KnowledgeGraph()

    def build(self, relationships: List[Relationship]) -> KnowledgeGraph:
        self._load_nodes()
        self._load_edges(relationships)
        log.info(f"Graph built: {self.graph.node_count} nodes, {self.graph.edge_count} edges.")
        return self.graph

    def _load_nodes(self):
        for category, objects in self.registry._data.items():
            for obj_id, obj in objects.items():
                self.graph.add_node(Node(obj_id=obj_id, category=category, data=obj))

    def _load_edges(self, relationships: List[Relationship]):
        for rel in relationships:
            if self.graph.find_node(rel.source_id) is None:
                log.warning(f"Edge skipped — source not in graph: {rel.source_id}")
                continue
            if self.graph.find_node(rel.target_id) is None:
                log.warning(f"Edge skipped — target not in graph: {rel.target_id}")
                continue
            edge = Edge(
                source_id=rel.source_id,
                target_id=rel.target_id,
                rel_type=str(rel.relationship_type),
                description=rel.description,
            )
            self.graph.add_edge(edge)

    @staticmethod
    def validate(graph: KnowledgeGraph) -> bool:
        ok, errors = GraphValidator(graph).validate()
        return ok
