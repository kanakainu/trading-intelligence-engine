"""Pack Loader — load, validate, and return compiled Knowledge Pack."""
import os, yaml, logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from core.compiler.pack_integrity import verify_integrity

log = logging.getLogger(__name__)

REQUIRED_FILES = ["manifest.yaml", "VERSION", "README.md", "CHANGELOG.md"]


@dataclass
class KnowledgePack:
    manifest: Dict[str, Any]
    version: str
    total_objects: int
    integrity_ok: bool
    categories: Dict[str, int] = field(default_factory=dict)

    def __repr__(self):
        return f"<KnowledgePack {self.manifest.get('name')} v{self.version} objects={self.total_objects} integrity={self.integrity_ok}>"


class PackLoader:
    def load(self, pack_dir: str) -> Optional[KnowledgePack]:
        # 1. Missing files check
        for f in REQUIRED_FILES:
            if not os.path.exists(os.path.join(pack_dir, f)):
                log.error(f"Missing required file: {f}")
                return None

        # 2. Load manifest
        with open(os.path.join(pack_dir, "manifest.yaml")) as f:
            manifest = yaml.safe_load(f)

        # 3. Version
        with open(os.path.join(pack_dir, "VERSION")) as f:
            version_text = f.read()
        version = None
        for line in version_text.splitlines():
            if line.startswith("Version"):
                version = line.split(":")[-1].strip()
        if not version:
            log.error("VERSION file missing version field")
            return None

        # 4. Manifest validation
        for field_name in ["pack_id","name","version","status","total_objects","integrity_sha256"]:
            if field_name not in manifest:
                log.error(f"Manifest missing field: {field_name}")
                return None

        # 5. Integrity check
        ok, msg = verify_integrity(pack_dir, manifest["integrity_sha256"])
        if not ok:
            log.warning(f"Pack integrity check: {msg}")
        else:
            log.info(f"Pack integrity check: {msg}")

        log.info(f"Pack loaded: {manifest.get('name')} v{version} objects={manifest.get('total_objects')}")
        return KnowledgePack(
            manifest=manifest,
            version=version,
            total_objects=manifest.get("total_objects", 0),
            integrity_ok=ok,
            categories=manifest.get("categories", {}),
        )
