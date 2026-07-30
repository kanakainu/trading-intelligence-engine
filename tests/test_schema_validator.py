import subprocess
import os
import pytest

SCHEMA_PATH = "/home/ubuntu/trading-intelligence-engine/core/schema/knowledge_schema.yaml"
VALIDATOR_PATH = "/home/ubuntu/trading-intelligence-engine/core/schema/schema_validator.py"
DUMMY_DIR = "/home/ubuntu/trading-intelligence-engine/knowledge/dummy"

@pytest.mark.parametrize("obj_file", [
    "concept.yaml",
    "structure.yaml",
    "location.yaml",
    "confirmation.yaml",
    "risk.yaml",
    "setup.yaml"
])
def test_dummy_validation(obj_file):
    obj_path = os.path.join(DUMMY_DIR, obj_file)
    result = subprocess.run(
        ["python3", VALIDATOR_PATH, SCHEMA_PATH, obj_path],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Valid" in result.stdout

def test_duplicate_id_failure():
    # Test validator directly
    from core.schema.schema_validator import SchemaValidator
    import yaml
    
    validator = SchemaValidator(SCHEMA_PATH)
    obj = {
        "id": "DUP01",
        "name": "Name 1",
        "category": "Concept",
        "version": "1.0",
        "status": "ACTIVE"
    }
    
    success, _ = validator.validate_object(obj)
    assert success is True
    
    # Try duplicate ID
    obj2 = obj.copy()
    obj2["name"] = "Name 2"
    success, msg = validator.validate_object(obj2)
    assert success is False
    assert "Duplicate ID" in msg

def test_invalid_category_failure():
    from core.schema.schema_validator import SchemaValidator
    validator = SchemaValidator(SCHEMA_PATH)
    obj = {
        "id": "CAT01",
        "name": "Name 1",
        "category": "InvalidCat",
        "version": "1.0",
        "status": "ACTIVE"
    }
    success, msg = validator.validate_object(obj)
    assert success is False
    assert "Invalid category" in msg
