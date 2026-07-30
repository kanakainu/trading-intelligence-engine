"""EpisodeWriter — writes completed trade episodes to HCK episodic memory."""
from typing import Any, Dict, Optional
from adapters.hck_bridge import HCKBridge


class EpisodeWriter:
    def __init__(self, bridge: HCKBridge):
        self._bridge = bridge

    def write(self, canonical_id: str, user_msg: str, bot_reply: str,
              metadata: Optional[Dict] = None) -> bool:
        return self._bridge.write_episode(canonical_id, user_msg, bot_reply, metadata)
