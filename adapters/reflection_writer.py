"""ReflectionWriter — writes analysis/reflection to HCK semantic memory."""
from adapters.hck_bridge import HCKBridge


class ReflectionWriter:
    def __init__(self, bridge: HCKBridge):
        self._bridge = bridge

    def write(self, canonical_id: str, content: str, category: str = "reflection") -> bool:
        return self._bridge.write_reflection(canonical_id, content, category)
