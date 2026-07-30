"""ContextValidator — health check for ImmutableContext completeness."""
from typing import Dict, List
from core.context.immutable_context import ImmutableContext


class ContextValidator:
    def validate(self, ctx: ImmutableContext) -> Dict[str, bool]:
        return {
            "context_available":    ctx is not None,
            "identity_available":   bool(ctx.identity),
            "goals_available":      len(ctx.goals) > 0,
            "semantic_available":   len(ctx.semantic_memory) > 0,
            "episodes_available":   len(ctx.recent_episodes) > 0,
            "reflections_available":len(ctx.recent_reflections) > 0,
        }

    def is_healthy(self, ctx: ImmutableContext) -> bool:
        checks = self.validate(ctx)
        # context + identity required; rest optional
        return checks["context_available"] and checks["identity_available"]
