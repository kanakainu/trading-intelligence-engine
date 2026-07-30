import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import yaml
from core.relationships.relationship import Relationship
from core.relationships.relationship_types import RelationshipType
from core.relationships.relationship_validator import RelationshipValidator

KNOWN_IDS = {"C001", "S001", "L001", "CF001", "R001", "ST001"}


@pytest.fixture
def validator():
    return RelationshipValidator(known_ids=set(KNOWN_IDS))


def make_rel(**kwargs):
    defaults = dict(
        source_id="S001", target_id="C001",
        relationship_type=RelationshipType.USED_BY,
        description="test"
    )
    defaults.update(kwargs)
    return Relationship(**defaults)


def test_valid_relationship(validator):
    ok, msg = validator.validate(make_rel())
    assert ok, msg


def test_unknown_source(validator):
    ok, msg = validator.validate(make_rel(source_id="UNKNOWN"))
    assert not ok
    assert "source_id not found" in msg


def test_unknown_target(validator):
    ok, msg = validator.validate(make_rel(target_id="UNKNOWN"))
    assert not ok
    assert "target_id not found" in msg


def test_duplicate_relationship(validator):
    rel = make_rel()
    validator.validate(rel)
    ok, msg = validator.validate(make_rel())
    assert not ok
    assert "duplicate" in msg


def test_circular_dependency(validator):
    validator.validate(make_rel(source_id="S001", target_id="C001",
                                relationship_type=RelationshipType.REQUIRES))
    ok, msg = validator.validate(make_rel(source_id="C001", target_id="S001",
                                          relationship_type=RelationshipType.REQUIRES))
    assert not ok
    assert "circular" in msg


def test_all_relationship_types(validator):
    ids = list(KNOWN_IDS)
    used = set()
    for i, rt in enumerate(RelationshipType):
        src, tgt = ids[i % len(ids)], ids[(i + 1) % len(ids)]
        key = (src, tgt, rt)
        if key in used:
            continue
        used.add(key)
        rel = Relationship(source_id=src, target_id=tgt, relationship_type=rt)
        ok, msg = validator.validate(rel)
        assert ok, f"{rt} failed: {msg}"


def test_dummy_relationships_yaml():
    path = os.path.join(os.path.dirname(__file__),
                        "../knowledge/dummy/dummy_relationships.yaml")
    with open(path) as f:
        data = yaml.safe_load(f)
    v = RelationshipValidator(known_ids=set(KNOWN_IDS))
    for r in data["relationships"]:
        rel = Relationship(
            source_id=r["source_id"],
            target_id=r["target_id"],
            relationship_type=RelationshipType(r["relationship_type"]),
            description=r.get("description", "")
        )
        ok, msg = v.validate(rel)
        assert ok, f"dummy rel failed: {rel} — {msg}"
