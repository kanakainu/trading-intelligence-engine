"""Test Sprint 2.11 — Knowledge Query Engine."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.query.query_engine import QueryEngine
from core.query.knowledge_query import KnowledgeQuery
from core.query.query_cache import QueryCache

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

@pytest.fixture(scope="module")
def qe():
    e = QueryEngine()
    e.build_from_dirs(BASE)
    return e

@pytest.fixture(scope="module")
def kq(qe):
    return KnowledgeQuery(qe)

def test_find_by_id(kq):
    r = kq.find_by_id("BYS-C001")
    assert r.success and r.object["id"] == "BYS-C001"

def test_find_unknown_id(kq):
    r = kq.find_by_id("BYS-XXXX")
    assert not r.success

def test_find_by_name(kq):
    r = kq.find_by_name("Impulse")
    assert r.success

def test_find_by_category(kq):
    results = kq.find_by_category("Structure")
    assert len(results) >= 15

def test_find_all(kq):
    results = kq.find_all("Concept")
    assert len(results) >= 50

def test_exists(kq):
    assert kq.exists("BYS-C001")
    assert not kq.exists("BYS-FAKE")

def test_dependencies(kq):
    deps = kq.dependencies("BYS-ST001")
    assert isinstance(deps, list)

def test_reverse_dependencies(kq):
    rdeps = kq.reverse_dependencies("BYS-C001")
    assert isinstance(rdeps, list)

def test_search(kq):
    results = kq.search("danger")
    assert len(results) >= 1
    names = [r.object["name"] for r in results if r.object]
    assert any("Danger" in n for n in names)

def test_explain(kq):
    r = kq.explain("BYS-CF026")
    assert r.success
    assert r.object is not None

def test_cache(qe):
    qe.find_by_id("BYS-C001")
    qe.find_by_id("BYS-C001")
    assert len(qe._cache) >= 1

def test_query_no_yaml_direct(kq):
    r = kq.find_by_id("BYS-C001")
    assert r.success  # reads from index, not filesystem
