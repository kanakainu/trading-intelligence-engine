"""Test Sprint 2.8 — Setup Schema Contract."""
import pytest, sys, os, yaml
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.setup.setup_schema_validator import SetupSchemaValidator
from core.setup.setup_compiler import SetupCompiler, SetupObject

SCHEMA_PATH   = os.path.abspath(os.path.join(os.path.dirname(__file__), "../core/schema/setup_schema.yaml"))
TEMPLATE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../knowledge/templates/setup_template.yaml"))

VALID = {
    "id": "TEST_001", "name": "Test Setup", "engine": "custom",
    "type": "LONG", "description": "A test setup.",
    "requires": ["OBJ_001"], "priority": 1, "confidence": 0.8,
}

@pytest.fixture
def v(): return SetupSchemaValidator(SCHEMA_PATH)
@pytest.fixture
def c(): return SetupCompiler(SCHEMA_PATH)

def test_valid_setup(v):           ok, e = v.validate(VALID); assert ok, e
def test_missing_field(v):         ok, e = v.validate({}); assert not ok; assert "missing_field:id" in e
def test_invalid_type(v):
    d = {**VALID, "type": "BUY"}; ok, e = v.validate(d); assert not ok; assert "invalid_type:BUY" in e
def test_confidence_range(v):
    d = {**VALID, "confidence": 1.5}; ok, e = v.validate(d); assert not ok
def test_all_types_valid(v):
    for t in ("LONG","SHORT","NEUTRAL"):
        ok, _ = v.validate({**VALID, "type": t}); assert ok
def test_compiler_returns_object(c, tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text(yaml.dump(VALID))
    obj = c.compile_file(str(p))
    assert isinstance(obj, SetupObject)
    assert obj.id == "TEST_001"
def test_compiler_rejects_invalid(c, tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.dump({"id": "X"}))
    assert c.compile_file(str(p)) is None
def test_template_valid(v):
    with open(TEMPLATE_PATH) as f: d = yaml.safe_load(f)
    ok, e = v.validate(d); assert ok, e
def test_no_engine_in_schema():
    """Schema must not hardcode methodology names."""
    import re
    with open(SCHEMA_PATH) as f: src = f.read()
    for bad in ["bystra","ict","smc","crt"]:
        assert not re.search(rf'\b{bad}\b', src, re.IGNORECASE), f"Found '{bad}' in schema"
