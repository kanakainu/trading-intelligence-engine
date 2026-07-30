"""SemanticReader — reads semantic memory from HCK."""
from typing import Any, Dict, List
from adapters.hck_bridge import HCKBridge


class SemanticReader:
    def __init__(self, bridge: HCKBridge):
        self._bridge = bridge

    def read(self, canonical_id: str, limit: int = 10) -> List[Dict]:
        return self._bridge.get_semantic_memory(canonical_id, limit=limit)
