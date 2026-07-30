import pytest
import os
import shutil
from unittest.mock import MagicMock

# Adjust Python path to import modules correctly
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..' )))

from core.compiler.knowledge_loader import KnowledgeLoader, KnowledgeObject, KnowledgeRegistry
from core.schema.schema_validator import SchemaValidator

# --- Fixtures for test environment setup ---
@pytest.fixture
def tie_base_path(tmp_path):
    # Create a dummy TIE base path
    base = tmp_path / "trading-intelligence-engine"
    base.mkdir()
    (base / "knowledge").mkdir()
    (base / "knowledge" / "dummy_pack").mkdir(parents=True, exist_ok=True)
    (base / "core" / "schema").mkdir(parents=True, exist_ok=True)

    # Create a dummy schema file
    schema_content = """
# TIE Knowledge Schema Definition v1.0
# Defines structure for all Knowledge Objects

base_fields:
  id: string
  name: string
  category: enum [Concept, Structure, Location, Confirmation, Risk, Setup]
  version: string
  status: enum [DRAFT, ACTIVE, DEPRECATED]
  description: string
  tags: list
  references: list
  metadata: dict

objects:
  Concept:
    required: [id, name, category, version, status]
  Structure:
    required: [id, name, category, version, status]
    optional: [characteristics]
  Location:
    required: [id, name, category, version, status]
    optional: [zone_type]
  Confirmation:
    required: [id, name, category, version, status]
    optional: [level]
  Risk:
    required: [id, name, category, version, status]
    optional: [risk_type]
  Setup:
    required: [id, name, category, version, status]
    optional: [requirements]
    """
    (base / "core" / "schema" / "knowledge_schema.yaml").write_text(schema_content)

    return base # Return Path object

@pytest.fixture
def schema_path(tie_base_path):
    return tie_base_path / "core" / "schema" / "knowledge_schema.yaml"

@pytest.fixture
def knowledge_pack_path(tie_base_path):
    return tie_base_path / "knowledge" / "dummy_pack"

@pytest.fixture
def loader(tie_base_path, schema_path):
    return KnowledgeLoader(str(tie_base_path), str(schema_path)) # Convert to string for loader

# --- Test cases ---
def test_load_empty_pack(loader, knowledge_pack_path, caplog):
    caplog.set_level(os.environ.get("LOG_LEVEL", "INFO"))
    loader.load_knowledge_pack(str(knowledge_pack_path)) # Convert to string for loader
    assert loader.registry.total_objects == 0
    assert "Scanning knowledge pack" in caplog.text

def test_load_single_object(loader, knowledge_pack_path, caplog):
    caplog.set_level(os.environ.get("LOG_LEVEL", "INFO"))
    obj_content = """
id: TEST001
name: Test Concept
category: Concept
version: 1.0
status: ACTIVE
description: A test concept.
    """
    (knowledge_pack_path / "test_concept.yaml").write_text(obj_content)
    
    loader.load_knowledge_pack(str(knowledge_pack_path))
    assert loader.registry.total_objects == 1
    assert loader.registry.count_by_category("Concept") == 1
    obj = loader.registry.get_by_id("Concept", "TEST001")
    assert obj.name == "Test Concept"
    assert "Loaded <Concept:TEST001 Test Concept>" in caplog.text

def test_load_multiple_objects_different_categories(loader, knowledge_pack_path):
    (knowledge_pack_path / "concept1.yaml").write_text("""
id: C001
name: Concept One
category: Concept
version: 1.0
status: ACTIVE
""")
    (knowledge_pack_path / "structure1.yaml").write_text("""
id: S001
name: Structure One
category: Structure
version: 1.0
status: ACTIVE
""")
    
    loader.load_knowledge_pack(str(knowledge_pack_path))
    assert loader.registry.total_objects == 2
    assert loader.registry.count_by_category("Concept") == 1
    assert loader.registry.count_by_category("Structure") == 1

def test_load_with_validation_failure(loader, knowledge_pack_path, caplog):
    caplog.set_level(os.environ.get("LOG_LEVEL", "INFO"))
    invalid_content = """
id: INVALID01
name: Invalid Object
category: NonExistentCategory
version: 1.0
status: ACTIVE
    """
    (knowledge_pack_path / "invalid.yaml").write_text(invalid_content)
    
    loader.load_knowledge_pack(str(knowledge_pack_path))
    assert loader.registry.total_objects == 0
    assert "Validation failed for" in caplog.text
    assert "Invalid category: NonExistentCategory" in caplog.text

def test_cache_mechanism(loader, knowledge_pack_path, caplog):
    caplog.set_level(os.environ.get("LOG_LEVEL", "DEBUG"))
    obj_content = """
id: CACHE001
name: Cache Test
category: Concept
version: 1.0
status: ACTIVE
    """
    obj_path = knowledge_pack_path / "cache_test.yaml"
    obj_path.write_text(obj_content)

    # First load
    loader.load_knowledge_pack(str(knowledge_pack_path))
    assert loader.registry.total_objects == 1
    assert "Loading and validating" in caplog.text
    caplog.clear()

    # Second load, should be skipped due to cache
    loader.load_knowledge_pack(str(knowledge_pack_path))
    assert loader.registry.total_objects == 1 # Still 1, not re-added
    assert "Skipping" in caplog.text
    assert "Loading and validating" not in caplog.text

    caplog.clear()
    # Modify file, should reload
    obj_path.write_text(obj_content + "\nmetadata: {new: value}")
    loader.load_knowledge_pack(str(knowledge_pack_path))
    assert loader.registry.total_objects == 1
    assert "Loading and validating" in caplog.text
    assert loader.registry.get_by_id("Concept", "CACHE001").metadata.get("new") == "value"

def test_load_all_packs(loader, tie_base_path, caplog):
    caplog.set_level(os.environ.get("LOG_LEVEL", "INFO"))
    # Create another dummy pack
    another_pack = tie_base_path / "knowledge" / "another_pack"
    another_pack.mkdir()
    (another_pack / "another_concept.yaml").write_text("""
id: AC001
name: Another Concept
category: Concept
version: 1.0
status: ACTIVE
""")
    
    # Clear previous registry entries to get accurate counts
    loader.registry = KnowledgeRegistry() 
    loader.load_all() # Load all packs

    assert loader.registry.total_objects >= 1 # At least one from another_pack
    assert loader.registry.count_by_category("Concept") >= 1
    assert "Loaded 1 Knowledge Objects in total." in caplog.text or "Loaded 2 Knowledge Objects in total." in caplog.text
    assert "Knowledge Loader: Validation Success for all loaded objects." in caplog.text
    


