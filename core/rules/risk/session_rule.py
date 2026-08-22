from datetime import datetime, timezone
from typing import Any, Dict, Optional
from core.rules.plugins.plugin_interface import RulePluginInterface, RuleResult

VALID_SESSIONS = {
    "LONDON":   (7, 16),
    "NEW_YORK": (12, 21),
    "ASIA":     (0, 9),
    "OVERLAP":  (12, 16),
    "CFD_EXT":  (21, 24),  # CFD extended hours (NY close to Asia open)
    "CFD_EARLY": (0, 7),   # CFD early hours (before Asia proper)
}


class SessionRule(RulePluginInterface):
    def initialize(self, config: Dict[str, Any]) -> None:
        self._allowed = [s.upper() for s in config.get("allowed_sessions", ["LONDON", "NEW_YORK"])]
        self._enabled = config.get("enabled", True)

    def evaluate(self, context, facts, setup_result=None, decision=None) -> RuleResult:
        now_utc = datetime.now(timezone.utc).hour
        active = [s for s, (start, end) in VALID_SESSIONS.items() if start <= now_utc < end]
        overlap = [s for s in active if s in self._allowed]
        if not overlap:
            return RuleResult("REJECT",
                f"No valid session active. Current={active}, allowed={self._allowed}",
                priority=self.priority())
        return RuleResult("APPROVE", f"Session OK: {overlap}", priority=self.priority())

    def metadata(self): return {"name": "session_rule", "type": "risk"}
    def priority(self) -> int: return 12
    def enabled(self) -> bool: return getattr(self, "_enabled", True)
