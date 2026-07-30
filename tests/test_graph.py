import pytest
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.graph.knowledge_graph import KnowledgeGraph, Node, Edge
from core.graph.graph_validator import GraphValidator
from core.graph.graph_builder import GraphBuilder
from core.compiler.knowledge_loader import KnowledgeRegistry, KnowledgeObject
from core.relationships.relationship import Relationship
from core.relationships.relationship_types import RelationshipType


# ── helpers ────────────────────────────────────────────────────────────────

def make_node(id_, cat="Concept"):
    return Node(obj_id=id_, category=cat, data=None)

def make_edge(src, tgt, rel="used_by"):
    return Edge(source_id=src, target_id=tgt, rel_type=rel)

def make_rel(src, tgt, rt=RelationshipType.USED_BY):
    return Relationship(source_id=src, target_id=tgt, relationship_type=rt)


# ── KnowledgeGraph unit tests ──────────────────────────────────────────────

def test_add_and_find_node():
    g = KnowledgeGraph()
    g.add_node(make_node("A"))
    assert g.find_node("A") is not None
    assert g.node_count == 1

def test_duplicate_node_skipped():
    g = KnowledgeGraph()
    g.add_node(make_node("A"))
    g.add_node(make_node("A"))
    assert g.node_count == 1

def test_remove_node_cleans_edges():
    g = KnowledgeGraph()
    g.add_node(make_node("A"))
    g.add_node(make_node("B"))
    g.add_edge(make_edge("A", "B"))
    g.remove_node("A")
    assert g.find_node("A") is None
    assert g.incoming("B") == []

def test_add_edge_and_neighbors():
    g = KnowledgeGraph()
    g.add_node(make_node("A"))
    g.add_node(make_node("B"))
    g.add_edge(make_edge("A", "B"))
    assert "B" in g.neighbors("A")
    assert "A" in g.neighbors("B")

def test_duplicate_edge_rejected():
    g = KnowledgeGraph()
    g.add_node(make_node("A"))
    g.add_node(make_node("B"))
    assert g.add_edge(make_edge("A", "B")) is True
    assert g.add_edge(make_edge("A", "B")) is False
    assert g.edge_count == 1

def test_remove_edge():
    g = KnowledgeGraph()
    g.add_node(make_node("A"))
    g.add_node(make_node("B"))
    g.add_edge(make_edge("A", "B"))
    g.remove_edge("A", "B", "used_by")
    assert g.edge_count == 0

def test_incoming_outgoing():
    g = KnowledgeGraph()
    for n in ["A", "B", "C"]:
        g.add_node(make_node(n))
    g.add_edge(make_edge("A", "B"))
    g.add_edge(make_edge("C", "B"))
    assert len(g.incoming("B")) == 2
    assert len(g.outgoing("A")) == 1

def test_json_dump():
    g = KnowledgeGraph()
    g.add_node(make_node("A"))
    g.add_node(make_node("B"))
    g.add_edge(make_edge("A", "B"))
    d = g.to_dict()
    assert len(d["nodes"]) == 2
    assert len(d["edges"]) == 1


# ── GraphValidator tests ────────────────────────────────────────────────────

def test_validator_orphan_detected():
    g = KnowledgeGraph()
    g.add_node(make_node("LONE"))
    ok, errors = GraphValidator(g).validate()
    assert not ok
    assert any("Orphan" in e for e in errors)

def test_validator_cycle_detected():
    g = KnowledgeGraph()
    for n in ["A", "B", "C"]:
        g.add_node(make_node(n))
    g.add_edge(make_edge("A", "B"))
    g.add_edge(make_edge("B", "C"))
    g.add_edge(make_edge("C", "A"))
    ok, errors = GraphValidator(g).validate()
    assert not ok
    assert any("Cycle" in e for e in errors)

def test_validator_clean_graph():
    g = KnowledgeGraph()
    g.add_node(make_node("A"))
    g.add_node(make_node("B"))
    g.add_edge(make_edge("A", "B"))
    ok, errors = GraphValidator(g).validate()
    assert ok, errors


# ── GraphBuilder integration test ──────────────────────────────────────────

def test_graph_builder_from_registry():
    reg = KnowledgeRegistry()
    for id_, cat in [("C001","Concept"), ("S001","Structure"), ("L001","Location")]:
        obj = KnowledgeObject(id=id_, name=f"Name {id_}", category=cat, version="1.0", status="ACTIVE")
        reg.add(obj, f"/fake/{id_}.yaml", "abc")

    rels = [
        make_rel("S001", "C001", RelationshipType.USED_BY),
        make_rel("L001", "C001", RelationshipType.DEPENDS_ON),
    ]
    builder = GraphBuilder(reg)
    graph = builder.build(rels)
    assert graph.node_count == 3
    assert graph.edge_count == 2
    assert graph.find_node("S001") is not None
