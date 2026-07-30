"""MemoryProvider — unified memory access interface for TIE."""
from typing import Any, Dict, List
from adapters.hck_bridge import HCKBridge


class MemoryProvider:
    def __init__(self, bridge: HCKBridge):
        self._bridge = bridge

    def get_episodic(self, canonical_id: str, limit: int = 5) -> List[Dict]:
        return self._bridge.get_recent_episodes(canonical_id, limit)

    def get_semantic(self, canonical_id: str, limit: int = 10) -> List[Dict]:
        return self._bridge.get_semantic_memory(canonical_id, limit)

    def get_goals(self, canonical_id: str) -> List[Dict]:
        return self._bridge.get_goals(canonical_id)
