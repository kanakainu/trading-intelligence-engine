"""ContextProvider — supplies TIE pipeline with HCK context."""
from typing import Any, Dict, Optional
from adapters.hck_bridge import HCKBridge


class ContextProvider:
    def __init__(self, bridge: HCKBridge):
        self._bridge = bridge

    def build_context(self, canonical_id: str, message: str = "") -> Dict[str, Any]:
        episodes = self._bridge.get_recent_episodes(canonical_id, limit=5)
        semantic  = self._bridge.get_semantic_memory(canonical_id, limit=10)
        identity  = self._bridge.get_identity(canonical_id)
        goals     = self._bridge.get_goals(canonical_id)
        return {
            "identity": identity,
            "goals": goals,
            "episodic": episodes,
            "semantic": semantic,
            "canonical_id": canonical_id,
        }
