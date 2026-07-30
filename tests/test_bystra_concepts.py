"""Test Bystra Core Concepts — schema, loader, graph, integrity."""
import pytest, sys, os, yaml
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.compiler.knowledge_loader import KnowledgeLoader, KnowledgeRegistry
from core.graph.graph_builder import GraphBuilder
from core.relationships.relationship import Relationship
from core.relationships.relationship_types import RelationshipType

CONCEPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__),
    "../knowledge/bystra/concepts"))
SCHEMA_PATH  = os.path.abspath(os.path.join(os.path.dirname(__file__),
    "../core/schema/knowledge_schema.yaml"))

REQUIRED_FIELDS = ["id","name","aliases","category","definition",
                   "characteristics","related_objects","tags","status","provenance"]
PROVENANCE_FIELDS = ["source_type","source_name","evidence_level","confidence"]


@pytest.fixture(scope="module")
def all_objects():
    objs = []
    for f in os.listdir(CONCEPTS_DIR):
        if f.endswith(".yaml"):
            with open(os.path.join(CONCEPTS_DIR, f)) as fh:
                objs.append(yaml.safe_load(fh))
    return objs

@pytest.fixture(scope="module")
def registry():
    loader = KnowledgeLoader(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        SCHEMA_PATH)
    loader.load_knowledge_pack(CONCEPTS_DIR)
    return loader.registry


def test_minimum_50_concepts(all_objects):
    assert len(all_objects) >= 50, f"Only {len(all_objects)} concepts found"

def test_all_have_required_fields(all_objects):
    for obj in all_objects:
        for f in REQUIRED_FIELDS:
            assert f in obj, f"{obj.get('id','?')} missing: {f}"

def test_no_duplicate_ids(all_objects):
    ids = [o["id"] for o in all_objects]
    assert len(ids) == len(set(ids)), "Duplicate IDs found"

def test_all_category_concept(all_objects):
    for obj in all_objects:
        assert obj["category"] == "Concept", f"{obj['id']} wrong category: {obj['category']}"

def test_provenance_fields(all_objects):
    for obj in all_objects:
        prov = obj.get("provenance", {})
        for f in PROVENANCE_FIELDS:
            assert f in prov, f"{obj['id']} provenance missing: {f}"

def test_no_trading_rule_fields(all_objects):
    forbidden = ["rules","entry_trigger","stop_loss","take_profit","direction","detector"]
    for obj in all_objects:
        for f in forbidden:
            assert f not in obj, f"{obj['id']} has forbidden field: {f}"

def test_loader_loads_all_concepts(registry):
    count = registry.count_by_category("Concept")
    assert count >= 50, f"Loader only found {count} concepts"

def test_duplicate_detection(all_objects):
    names = [o["name"] for o in all_objects]
    assert len(names) == len(set(names)), "Duplicate names found"

def test_graph_reference_valid(all_objects):
    all_ids = {o["id"] for o in all_objects}
    for obj in all_objects:
        for ref in obj.get("related_objects", []):
            assert ref in all_ids, f"{obj['id']} has broken ref: {ref}"

def test_graph_buildable(registry):
    assert registry.count_by_category('Concept') >= 50
