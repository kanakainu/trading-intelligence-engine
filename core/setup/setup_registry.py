"""Setup Registry — register/list/get/unregister setup definitions."""
import logging
from typing import Dict, List, Optional, Any

log = logging.getLogger(__name__)


class SetupRegistry:
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def register(self, setup_def: Dict[str, Any]) -> None:
        sid = setup_def.get("id")
        if not sid:
            raise ValueError("setup_def must have 'id'")
        self._store[sid] = setup_def
        log.info(f"Setup registered: {sid}")

    def unregister(self, setup_id: str) -> None:
        self._store.pop(setup_id, None)

    def get(self, setup_id: str) -> Optional[Dict[str, Any]]:
        return self._store.get(setup_id)

    def list(self) -> List[str]:
        return list(self._store.keys())

    def exists(self, setup_id: str) -> bool:
        return setup_id in self._store
