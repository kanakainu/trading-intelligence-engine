"""Test Bystra Locations."""
import pytest, sys, os, yaml
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.compiler.knowledge_loader import KnowledgeLoader
from core.graph.graph_builder import GraphBuilder

LOC_DIR     = os.path.abspath(os.path.join(os.path.dirname(__file__), "../knowledge/bystra/locations"))
SCHEMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../core/schema/knowledge_schema.yaml"))
CON_DIR     = os.path.abspath(os.path.join(os.path.dirname(__file__), "../knowledge/bystra/concepts"))
STR_DIR     = os.path.abspath(os.path.join(os.path.dirname(__file__), "../knowledge/bystra/structures"))

REQUIRED = ["id","name","aliases","category","version","definition",
            "location_type","characteristics","related_objects","used_by","tags","status","provenance"]

@pytest.fixture(scope="module")
def all_locs():
    return [yaml.safe_load(open(os.path.join(LOC_DIR, f)))
            for f in os.listdir(LOC_DIR) if f.endswith(".yaml")]

@pytest.fixture(scope="module")
def registry():
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    loader = KnowledgeLoader(base, SCHEMA_PATH)
    for d in [CON_DIR, STR_DIR, LOC_DIR]:
        loader.load_knowledge_pack(d)
    return loader.registry

def test_minimum_20_locations(all_locs):
    assert len(all_locs) >= 20

def test_required_fields(all_locs):
    for obj in all_locs:
        for f in REQUIRED:
            assert f in obj, f"{obj.get('id')} missing: {f}"

def test_no_duplicate_ids(all_locs):
    ids = [o["id"] for o in all_locs]
    assert len(ids) == len(set(ids))

def test_no_trading_rules(all_locs):
    for obj in all_locs:
        for f in ["entry_trigger","stop_loss","take_profit","BUY","SELL","rules"]:
            assert f not in obj, f"{obj['id']} forbidden: {f}"

def test_location_type_set(all_locs):
    valid = {"SUPPORT","RESISTANCE","DEMAND","SUPPLY","QUALITY","REFERENCE",
             "CONFIRMATION_ZONE","RELATIVE_POSITION","LIQUIDITY","RISK"}
    for obj in all_locs:
        assert obj["location_type"] in valid, f"{obj['id']} bad location_type: {obj['location_type']}"

def test_loader_loads(registry):
    assert registry.count_by_category("Location") >= 20

def test_graph_buildable(registry):
    g = GraphBuilder(registry).build([])
    assert registry.count_by_category('Location') >= 20

def test_refs_valid(all_locs):
    concept_ids = {f"BYS-C{str(i).zfill(3)}" for i in range(1,51)}
    struct_ids  = {f"BYS-ST{str(i).zfill(3)}" for i in range(1,16)}
    loc_ids     = {o["id"] for o in all_locs}
    valid = concept_ids | struct_ids | loc_ids
    for obj in all_locs:
        for ref in obj.get("related_objects", []):
            assert ref in valid, f"{obj['id']} broken ref: {ref}"
