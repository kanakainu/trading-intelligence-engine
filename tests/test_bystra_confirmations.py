"""Test Bystra Confirmations."""
import pytest, sys, os, yaml
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.compiler.knowledge_loader import KnowledgeLoader
from core.graph.graph_builder import GraphBuilder

CF_DIR      = os.path.abspath(os.path.join(os.path.dirname(__file__), "../knowledge/bystra/confirmations"))
SCHEMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../core/schema/knowledge_schema.yaml"))
CON_DIR     = os.path.abspath(os.path.join(os.path.dirname(__file__), "../knowledge/bystra/concepts"))
STR_DIR     = os.path.abspath(os.path.join(os.path.dirname(__file__), "../knowledge/bystra/structures"))
LOC_DIR     = os.path.abspath(os.path.join(os.path.dirname(__file__), "../knowledge/bystra/locations"))

REQUIRED = ["id","name","aliases","category","version","definition","characteristics",
            "strengthens","related_objects","used_by","tags","status","provenance"]

@pytest.fixture(scope="module")
def all_cfs():
    return [yaml.safe_load(open(os.path.join(CF_DIR, f)))
            for f in os.listdir(CF_DIR) if f.endswith(".yaml")]

@pytest.fixture(scope="module")
def registry():
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    loader = KnowledgeLoader(base, SCHEMA_PATH)
    for d in [CON_DIR, STR_DIR, LOC_DIR, CF_DIR]:
        loader.load_knowledge_pack(d)
    return loader.registry

def test_minimum_25(all_cfs):      assert len(all_cfs) >= 25
def test_required_fields(all_cfs):
    for o in all_cfs:
        for f in REQUIRED: assert f in o, f"{o.get('id')} missing: {f}"
def test_no_dup_ids(all_cfs):
    ids = [o["id"] for o in all_cfs]; assert len(ids) == len(set(ids))
def test_no_trading_rules(all_cfs):
    for o in all_cfs:
        for f in ["entry_trigger","stop_loss","take_profit","BUY","SELL","rules","scoring"]:
            assert f not in o, f"{o['id']} forbidden: {f}"
def test_loader(registry):         assert registry.count_by_category("Confirmation") >= 25
def test_graph(registry):
    assert registry.count_by_category('Confirmation') >= 25
def test_refs_valid(all_cfs):
    cf_ids  = {o["id"] for o in all_cfs}
    c_ids   = {f"BYS-C{str(i).zfill(3)}"  for i in range(1,51)}
    st_ids  = {f"BYS-ST{str(i).zfill(3)}" for i in range(1,16)}
    l_ids   = {f"BYS-L{str(i).zfill(3)}"  for i in range(1,22)}
    valid   = cf_ids | c_ids | st_ids | l_ids
    for o in all_cfs:
        for ref in o.get("related_objects", []) + o.get("strengthens", []):
            assert ref in valid, f"{o['id']} broken ref: {ref}"
