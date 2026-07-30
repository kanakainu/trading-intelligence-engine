"""ImmutableContext — frozen Context Object from HCK. Read-only."""
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class ImmutableContext:
    identity: Dict[str, Any]
    goals: tuple          # List[Dict] as tuple for hashability
    semantic_memory: tuple
    recent_episodes: tuple
    recent_reflections: tuple
    active_session: str
    metadata: Dict[str, Any]
    canonical_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity": self.identity,
            "goals": list(self.goals),
            "semantic_memory": list(self.semantic_memory),
            "recent_episodes": list(self.recent_episodes),
            "recent_reflections": list(self.recent_reflections),
            "active_session": self.active_session,
            "metadata": self.metadata,
            "canonical_id": self.canonical_id,
        }

    def is_valid(self) -> bool:
        return bool(self.canonical_id)
