"""Test Sprint 2.12 — Pack Integrity & Loader."""
import pytest, sys, os, yaml
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.compiler.pack_loader import PackLoader, KnowledgePack
from core.compiler.pack_integrity import compute_pack_sha, compute_fingerprint, verify_integrity

BYSTRA = os.path.abspath(os.path.join(os.path.dirname(__file__), "../knowledge/bystra"))

@pytest.fixture(scope="module")
def pack():
    return PackLoader().load(BYSTRA)

def test_pack_load_success(pack):
    assert pack is not None
    assert isinstance(pack, KnowledgePack)

def test_manifest_valid(pack):
    for f in ["pack_id","name","version","status","total_objects","integrity_sha256"]:
        assert f in pack.manifest

def test_version_valid(pack):
    assert pack.version == "1.0.0"

def test_integrity_pass(pack):
    assert pack.integrity_ok

def test_object_count_consistent(pack):
    assert pack.total_objects == 164

def test_categories_present(pack):
    for cat in ["Concept","Structure","Location","Confirmation","Risk","Setup"]:
        assert pack.categories.get(cat, 0) > 0

def test_missing_manifest(tmp_path):
    result = PackLoader().load(str(tmp_path))
    assert result is None

def test_missing_version(tmp_path):
    (tmp_path / "manifest.yaml").write_text("pack_id: x\nname: x\nversion: 1.0\nstatus: LOCKED\ntotal_objects: 0\nintegrity_sha256: abc\n")
    (tmp_path / "README.md").write_text("r")
    (tmp_path / "CHANGELOG.md").write_text("c")
    result = PackLoader().load(str(tmp_path))
    assert result is None  # missing VERSION file

def test_invalid_manifest(tmp_path):
    (tmp_path / "manifest.yaml").write_text("name: x\n")
    (tmp_path / "VERSION").write_text("Version : 1.0.0\n")
    (tmp_path / "README.md").write_text("r")
    (tmp_path / "CHANGELOG.md").write_text("c")
    result = PackLoader().load(str(tmp_path))
    assert result is None
