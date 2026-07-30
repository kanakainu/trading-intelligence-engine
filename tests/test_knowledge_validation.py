"""Test Sprint 2.10 — Knowledge Pack Validation."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.validator.integrity_validator import IntegrityValidator
from core.validator.dependency_validator import DependencyValidator
from core.validator.relationship_validator import RelationshipValidator
from core.validator.knowledge_validator import validate_bystra

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# ── unit tests ─────────────────────────────────────────────────────────────

def test_duplicate_id():
    iv = IntegrityValidator()
    objs = [{"id":"A","name":"N1"},{"id":"A","name":"N2"}]
    errs = iv.check_duplicates(objs)
    assert any("DUPLICATE_ID:A" in e for e in errs)

def test_no_duplicates():
    iv = IntegrityValidator()
    errs = iv.check_duplicates([{"id":"A","name":"N1"},{"id":"B","name":"N2"}])
    assert not errs

def test_missing_reference():
    dv = DependencyValidator({"BYS-C001"})
    errs = dv.check({"id":"X","requires":["BYS-C001","BYS-C999"]})
    assert any("BYS-C999" in e for e in errs)

def test_valid_references():
    dv = DependencyValidator({"BYS-C001","BYS-C002"})
    errs = dv.check({"id":"X","requires":["BYS-C001","BYS-C002"]})
    assert not errs

def test_broken_relationship_no_bys_prefix():
    dv = DependencyValidator({"BYS-C001"})
    # non-BYS refs not checked
    errs = dv.check({"id":"X","requires":["Strong Support","HTF Confirmation"]})
    assert not errs

def test_circular_dependency():
    rv = RelationshipValidator()
    graph = {"A":["B"],"B":["C"],"C":["A"]}
    cycles = rv.check_circular(graph)
    assert any("CIRCULAR" in c for c in cycles)

def test_no_circular():
    rv = RelationshipValidator()
    graph = {"A":["B"],"B":["C"]}
    assert not rv.check_circular(graph)

def test_orphan_detection():
    iv = IntegrityValidator()
    all_ids = {"BYS-C001","BYS-C002","BYS-C003"}
    referenced = {"BYS-C001","BYS-C002"}
    warnings = iv.check_orphans(all_ids, referenced)
    assert any("ORPHAN:BYS-C003" in w for w in warnings)

# ── integration: full Bystra pack ─────────────────────────────────────────

@pytest.fixture(scope="module")
def report():
    return validate_bystra(BASE)

def test_pack_has_all_categories(report):
    for cat in ["Concept","Structure","Location","Confirmation","Risk","Setup"]:
        assert report.counts.get(cat, 0) > 0

def test_no_errors(report):
    assert not report.errors, f"Errors found: {report.errors[:5]}"

def test_status_pass(report):
    assert report.status == "PASS"

def test_report_prints(report):
    text = report.print()
    assert "STATUS: PASS" in text
    assert "Total Objects" in text
