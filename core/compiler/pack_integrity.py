"""Pack Integrity — SHA256 fingerprint + object count validation."""
import os, yaml, hashlib, json
from typing import Dict, Tuple


def compute_fingerprint(pack_dir: str) -> Dict[str, str]:
    fp = {}
    for subdir, _, files in os.walk(pack_dir):
        for f in sorted(files):
            if f.endswith(".yaml") and not f in ("manifest.yaml","PACK_INFO.yaml"):
                path = os.path.join(subdir, f)
                with open(path, "rb") as fh:
                    fp[os.path.relpath(path, pack_dir)] = hashlib.sha256(fh.read()).hexdigest()
    return fp


def compute_pack_sha(fingerprints: Dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(fingerprints, sort_keys=True).encode()).hexdigest()


def verify_integrity(pack_dir: str, manifest_sha: str) -> Tuple[bool, str]:
    fp = compute_fingerprint(pack_dir)
    actual = compute_pack_sha(fp)
    if actual == manifest_sha:
        return True, f"PASS sha={actual[:16]}..."
    return False, f"MISMATCH expected={manifest_sha[:16]}... got={actual[:16]}..."
