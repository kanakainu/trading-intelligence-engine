"""Test Bystra Risks."""
import pytest, sys, os, yaml
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.compiler.knowledge_loader import KnowledgeLoader

RISKS_DIR   = os.path.abspath(os.path.join(os.path.dirname(__file__), "../knowledge/bystra/risks"))
SCHEMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../core/schema/knowledge_schema.yaml"))

REQUIRED = ["id","name","aliases","category","version","definition","severity",
            "characteristics","affects","related_objects","tags","status","provenance"]
VALID_SEVERITY = {"LOW","MEDIUM","HIGH","CRITICAL"}

@pytest.fixture(scope="module")
def all_risks():
    return [yaml.safe_load(open(os.path.join(RISKS_DIR, f)))
            for f in os.listdir(RISKS_DIR) if f.endswith(".yaml")]

@pytest.fixture(scope="module")
def registry():
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    loader = KnowledgeLoader(base, SCHEMA_PATH)
    loader.load_knowledge_pack(RISKS_DIR)
    return loader.registry

def test_minimum_20(all_risks):       assert len(all_risks) >= 20
def test_required_fields(all_risks):
    for o in all_risks:
        for f in REQUIRED: assert f in o, f"{o.get('id')} missing: {f}"
def test_no_dup_ids(all_risks):
    ids = [o["id"] for o in all_risks]; assert len(ids) == len(set(ids))
def test_severity_valid(all_risks):
    for o in all_risks: assert o["severity"] in VALID_SEVERITY
def test_no_trading_rules(all_risks):
    for o in all_risks:
        for f in ["BUY","SELL","entry","lot_size","stop_loss_formula","take_profit_formula"]:
            assert f not in o, f"{o['id']} forbidden: {f}"
def test_loader(registry):            assert registry.count_by_category("Risk") >= 20
def test_no_mm_logic(all_risks):
    for o in all_risks:
        definition = o.get("definition","").lower()
        for bad in ["position sizing","lot size calculation","risk reward formula"]:
            assert bad not in definition, f"{o['id']} has MM logic: {bad}"
