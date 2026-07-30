"""Test Bystra Entry Patterns."""
import pytest, sys, os, yaml
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.compiler.knowledge_loader import KnowledgeLoader

EP_DIR      = os.path.abspath(os.path.join(os.path.dirname(__file__), "../knowledge/bystra/entry_patterns"))
SCHEMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../core/schema/knowledge_schema.yaml"))

REQUIRED = ["id","name","aliases","category","version","definition","trigger_description",
            "prerequisites","invalidation","related_objects","used_by","tags","status","provenance"]

@pytest.fixture(scope="module")
def all_eps():
    return [yaml.safe_load(open(os.path.join(EP_DIR, f)))
            for f in os.listdir(EP_DIR) if f.endswith(".yaml")]

@pytest.fixture(scope="module")
def registry():
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    l = KnowledgeLoader(base, SCHEMA_PATH)
    l.load_knowledge_pack(EP_DIR)
    return l.registry

def test_minimum_15(all_eps):       assert len(all_eps) >= 15
def test_required_fields(all_eps):
    for o in all_eps:
        for f in REQUIRED: assert f in o, f"{o.get('id')} missing: {f}"
def test_no_dup_ids(all_eps):
    ids = [o["id"] for o in all_eps]; assert len(ids) == len(set(ids))
def test_no_numeric_rules(all_eps):
    forbidden = ["BUY","SELL","stop_loss","take_profit","lot_size","scoring","threshold"]
    for o in all_eps:
        for f in forbidden: assert f not in o, f"{o['id']} forbidden: {f}"
def test_trigger_is_conceptual(all_eps):
    for o in all_eps:
        t = o.get("trigger_description","")
        assert len(t) > 10, f"{o['id']} trigger too short"
def test_loader(registry):          assert registry.count_by_category("Concept") >= 16
