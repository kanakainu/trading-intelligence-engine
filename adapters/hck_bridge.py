"""HCKBridge — single boundary between TIE and HCK.
All other TIE modules import only this file, never hck_service directly.
No reasoning, no trading logic, no DB access.
"""
import sys
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

log = logging.getLogger("HCKBridge")

_HCK_PATH = "/home/ubuntu/.hermes/scripts"


def _load_hck():
    if _HCK_PATH not in sys.path:
        sys.path.insert(0, _HCK_PATH)
    from hck_service import HCKService
    return HCKService()


class HCKBridge:
    """
    TIE ↔ HCK boundary layer.
    Only this class knows about HCK internals.
    All TIE modules talk to HCKBridge, never to HCKService directly.
    """

    def __init__(self, workspace: str = "boskuh", agent_id: str = "riri"):
        self._workspace = workspace
        self._agent_id = agent_id
        self._client: Any = None
        self._connected = False

    def initialize(self) -> None:
        try:
            self._client = _load_hck()
            self._connected = True
            log.info("HCKBridge connected to HCKService")
        except Exception as e:
            self._connected = False
            log.warning(f"HCKBridge failed to connect: {e}")

    def health_check(self) -> Dict[str, Any]:
        ok = self._connected and self._client is not None
        return {
            "connected": ok,
            "memory_available": ok,
            "reflection_writer_ready": ok,
            "episode_writer_ready": ok,
            "context_provider_ready": ok,
            "status": "HEALTHY" if ok else "DISCONNECTED",
        }

    # ── Context ────────────────────────────────────────────────────────────
    def get_context(self, canonical_id: str, message: str = "") -> Dict[str, Any]:
        if not self._client: return {}
        try:
            episodes = self.get_recent_episodes(canonical_id)
            semantic = self.get_semantic_memory(canonical_id)
            return {
                "episodic": episodes,
                "semantic": semantic,
                "canonical_id": canonical_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            log.warning(f"get_context failed: {e}")
            return {}

    def get_recent_episodes(self, canonical_id: str, limit: int = 5) -> List[Dict]:
        if not self._client: return []
        try:
            return self._client.get_episodic_memory(canonical_id, limit=limit,
                                                    agent_id=self._agent_id)
        except Exception as e:
            log.warning(f"get_recent_episodes failed: {e}")
            return []

    def get_semantic_memory(self, canonical_id: str, limit: int = 10) -> List[Dict]:
        if not self._client: return []
        try:
            return self._client.get_semantic_memory(canonical_id, limit=limit,
                                                    agent_id=self._agent_id)
        except Exception as e:
            log.warning(f"get_semantic_memory failed: {e}")
            return []

    def get_identity(self, lid: str) -> Dict[str, Any]:
        if not self._client: return {}
        try:
            return self._client.get_contact(lid) or {}
        except Exception as e:
            log.warning(f"get_identity failed: {e}")
            return {}

    def get_goals(self, canonical_id: str) -> List[Dict]:
        """Goals stored as semantic memory with category='goal'."""
        memories = self.get_semantic_memory(canonical_id)
        return [m for m in memories if m.get("category") == "goal"]

    # ── Writers ────────────────────────────────────────────────────────────
    def write_episode(self, canonical_id: str, user_msg: str, bot_reply: str,
                      metadata: Optional[Dict] = None) -> bool:
        if not self._client: return False
        try:
            self._client.store_turn(canonical_id, user_msg, bot_reply,
                                    agent_id=self._agent_id)
            return True
        except Exception as e:
            log.warning(f"write_episode failed: {e}")
            return False

    def write_reflection(self, canonical_id: str, content: str,
                         category: str = "reflection") -> bool:
        if not self._client: return False
        try:
            self._client.store_semantic(canonical_id, content, category=category,
                                        agent_id=self._agent_id)
            return True
        except Exception as e:
            log.warning(f"write_reflection failed: {e}")
            return False

    def publish_event(self, event_type: str, payload: Dict[str, Any]) -> bool:
        """Publish trading event to HCK as a semantic memory entry."""
        if not self._client: return False
        try:
            canonical_id = payload.get("canonical_id", "system")
            content = f"[TIE_EVENT:{event_type}] {payload}"
            return self.write_reflection(canonical_id, content, category="trading_event")
        except Exception as e:
            log.warning(f"publish_event failed: {e}")
            return False

    def close(self) -> None:
        self._client = None
        self._connected = False
