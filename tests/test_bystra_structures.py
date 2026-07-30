"""Test Bystra Structures — schema, loader, integrity."""
import pytest, sys, os, yaml
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.compiler.knowledge_loader import KnowledgeLoader
from core.graph.graph_builder import GraphBuilder

STRUCTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__),
    "../knowledge/bystra/structures"))
SCHEMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__),
    "../core/schema/knowledge_schema.yaml"))
CONCEPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__),
    "../knowledge/bystra/concepts"))

REQUIRED = ["id","name","aliases","category","version","abstraction_level",
            "definition","sequence","components","characteristics",
            "invalidation","related_objects","used_by","tags","status","provenance"]

@pytest.fixture(scope="module")
def all_structs():
    return [yaml.safe_load(open(os.path.join(STRUCTS_DIR, f)))
            for f in os.listdir(STRUCTS_DIR) if f.endswith(".yaml")]

@pytest.fixture(scope="module")
def registry():
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    loader = KnowledgeLoader(base, SCHEMA_PATH)
    loader.load_knowledge_pack(CONCEPTS_DIR)
    loader.load_knowledge_pack(STRUCTS_DIR)
    return loader.registry

def test_minimum_15_structures(all_structs):
    assert len(all_structs) >= 15

def test_required_fields(all_structs):
    for obj in all_structs:
        for f in REQUIRED:
            assert f in obj, f"{obj.get('id')} missing: {f}"

def test_abstraction_level(all_structs):
    for obj in all_structs:
        assert obj["abstraction_level"] == "STRUCTURE"

def test_no_duplicate_ids(all_structs):
    ids = [o["id"] for o in all_structs]
    assert len(ids) == len(set(ids))

def test_no_trading_rules(all_structs):
    forbidden = ["entry_trigger","stop_loss","take_profit","direction","BUY","SELL","rules"]
    for obj in all_structs:
        for f in forbidden:
            assert f not in obj, f"{obj['id']} has forbidden field: {f}"

def test_sequence_is_list(all_structs):
    for obj in all_structs:
        assert isinstance(obj["sequence"], list), f"{obj['id']} sequence not list"
        assert len(obj["sequence"]) >= 2

def test_loader_loads_structures(registry):
    assert registry.count_by_category("Structure") >= 15

def test_graph_buildable(registry):
    graph = GraphBuilder(registry).build([])
    assert registry.count_by_category('Structure') >= 15

def test_related_refs_valid(all_structs):
    all_ids = {o["id"] for o in all_structs}
    concept_ids = {f"BYS-C{str(i).zfill(3)}" for i in range(1, 51)}
    valid_ids = all_ids | concept_ids
    for obj in all_structs:
        for ref in obj.get("related_objects", []):
            assert ref in valid_ids, f"{obj['id']} broken ref: {ref}"
