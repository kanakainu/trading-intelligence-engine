"""ContextCache — session-scoped cache. Auto-invalidates on session change."""
from typing import Optional
from core.context.immutable_context import ImmutableContext


class ContextCache:
    def __init__(self):
        self._cache: Optional[ImmutableContext] = None
        self._session: str = ""

    def get(self, session: str) -> Optional[ImmutableContext]:
        if self._session == session and self._cache is not None:
            return self._cache
        return None

    def set(self, session: str, ctx: ImmutableContext) -> None:
        self._session = session
        self._cache = ctx

    def invalidate(self) -> None:
        self._cache = None
        self._session = ""

    @property
    def hit(self) -> bool:
        return self._cache is not None
