"""Test Bystra ontology — all categories loadable via KnowledgeLoader."""
import pytest, sys, os, yaml
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

ONTOLOGY_PATH = os.path.join(os.path.dirname(__file__),
    "../knowledge/bystra/ontology/ontology.yaml")

REQUIRED_CATEGORIES = [
    "Concept", "Structure", "Location", "Confirmation", "Risk",
    "Entry Pattern", "Setup", "Exit", "Market Condition",
    "Liquidity", "Trend", "Session", "Timeframe",
]
REQUIRED_FIELDS = ["id", "name", "category", "description", "aliases", "tags"]


@pytest.fixture(scope="module")
def ontology():
    with open(ONTOLOGY_PATH) as f:
        return yaml.safe_load(f)


def test_taxonomy_defined(ontology):
    assert "categories" in ontology
    for cat in REQUIRED_CATEGORIES:
        assert cat in ontology["categories"], f"Missing category: {cat}"

def test_objects_exist(ontology):
    assert "objects" in ontology
    assert len(ontology["objects"]) >= 10

def test_all_objects_have_required_fields(ontology):
    for obj in ontology["objects"]:
        for field in REQUIRED_FIELDS:
            assert field in obj, f"{obj.get('id','?')} missing: {field}"

def test_all_categories_represented(ontology):
    found = {o["category"] for o in ontology["objects"]}
    for cat in REQUIRED_CATEGORIES:
        assert cat in found, f"No object for category: {cat}"

def test_no_duplicate_ids(ontology):
    ids = [o["id"] for o in ontology["objects"]]
    assert len(ids) == len(set(ids)), "Duplicate IDs found"

def test_no_trading_rule_in_ontology(ontology):
    """Ontology must be pure taxonomy — no rule/logic fields."""
    forbidden = ["rules", "entry_trigger", "stop_loss", "take_profit", "direction"]
    for obj in ontology["objects"]:
        for f in forbidden:
            assert f not in obj, f"{obj['id']} has forbidden field: {f}"
