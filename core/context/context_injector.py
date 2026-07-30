"""ContextInjector — builds ImmutableContext from HCK via HCKBridge."""
import logging
from typing import Any, Optional
from core.context.immutable_context import ImmutableContext
from core.context.context_cache import ContextCache
from core.context.context_validator import ContextValidator

log = logging.getLogger("ContextInjector")


class ContextInjector:
    """
    Reads Context from HCK. Returns ImmutableContext.
    TIE modules consume this — never modify it.
    """

    def __init__(self, hck_bridge: Any):
        self._hck = hck_bridge
        self._cache = ContextCache()
        self._validator = ContextValidator()

    def inject(self, canonical_id: str, session: str = "") -> ImmutableContext:
        """Build or return cached ImmutableContext for this trading session."""
        cached = self._cache.get(session)
        if cached:
            log.debug(f"ContextInjector cache hit: {canonical_id}/{session}")
            return cached

        # Fetch from HCK
        identity    = self._safe(lambda: self._hck.get_identity(canonical_id), {})
        goals       = self._safe(lambda: self._hck.get_goals(canonical_id), [])
        semantic    = self._safe(lambda: self._hck.get_semantic_memory(canonical_id), [])
        episodes    = self._safe(lambda: self._hck.get_recent_episodes(canonical_id), [])
        reflections = self._safe(
            lambda: [m for m in self._hck.get_semantic_memory(canonical_id, limit=5)
                     if m.get("category") == "reflection"], [])

        ctx = ImmutableContext(
            identity=identity or {},
            goals=tuple(goals),
            semantic_memory=tuple(semantic),
            recent_episodes=tuple(episodes),
            recent_reflections=tuple(reflections),
            active_session=session,
            metadata={"source": "hck", "canonical_id": canonical_id},
            canonical_id=canonical_id,
        )
        if session:
            self._cache.set(session, ctx)
        log.info(f"ContextInjector built: {canonical_id} "
                 f"eps={len(episodes)} sem={len(semantic)} goals={len(goals)}")
        return ctx

    def health_check(self, canonical_id: str, session: str = "") -> dict:
        ctx = self.inject(canonical_id, session)
        return self._validator.validate(ctx)

    def invalidate(self) -> None:
        self._cache.invalidate()

    @staticmethod
    def _safe(fn, default):
        try:
            return fn()
        except Exception as e:
            log.warning(f"ContextInjector fetch failed (non-fatal): {e}")
            return default
