"""Test Bystra Setup Definitions — Sprint 2.9."""
import pytest, sys, os, yaml
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.setup.setup_compiler import SetupCompiler, SetupObject

SETUPS_DIR  = os.path.abspath(os.path.join(os.path.dirname(__file__), "../knowledge/bystra/setups"))
SCHEMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../core/schema/setup_schema.yaml"))

REQUIRED = ["id","name","engine","category","version","setup_type","description",
            "allowed_entry_patterns","required_structures","required_concepts",
            "invalidate_conditions","references","provenance"]

@pytest.fixture(scope="module")
def all_setups():
    return [yaml.safe_load(open(os.path.join(SETUPS_DIR, f)))
            for f in sorted(os.listdir(SETUPS_DIR)) if f.endswith(".yaml")]

@pytest.fixture(scope="module")
def compiled():
    c = SetupCompiler(SCHEMA_PATH)
    return c.compile_dir(SETUPS_DIR)

def test_13_setups(all_setups):         assert len(all_setups) == 13
def test_required_fields(all_setups):
    for o in all_setups:
        for f in REQUIRED: assert f in o, f"{o.get('id')} missing: {f}"
def test_no_dup_ids(all_setups):
    ids = [o["id"] for o in all_setups]; assert len(ids) == len(set(ids))
def test_no_python_logic(all_setups):
    # Check string VALUES (definitions, descriptions) not field keys
    for o in all_setups:
        for check_field in ["description","notes"]:
            text = o.get(check_field, "")
            for bad in ["def ", "import ", "while ", "return ", "lambda "]:
                assert bad not in text, f"{o['id']}.{check_field} has code: {bad}"
def test_all_engine_bystra(all_setups):
    for o in all_setups: assert o["engine"] == "bystra"
def test_compiler_compiles_all(compiled):
    assert len(compiled) == 13
    for obj in compiled: assert isinstance(obj, SetupObject)
def test_references_from_doc(all_setups):
    for o in all_setups:
        refs = o.get("references", [])
        assert len(refs) >= 1, f"{o['id']} missing references"
        assert "XAUUSD Bystra Secret Strategy" in refs[0]
def test_setup_names(all_setups):
    names = {o["name"] for o in all_setups}
    expected = {"Hybrid 1","Hybrid 2","SNRC1","SNRC2","SNRC3",
                "QMR","QMC","QM2P","QMM","Blindspot","Blindspot 2","Manipulation","CLAB"}
    assert names == expected
