"""NewsFilterPlugin — REJECT if active news blackout window."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from core.rules.plugins.plugin_interface import RulePluginInterface, RuleResult

BLACKOUT_KEYWORDS = ("NFP", "CPI", "FOMC", "NONFARM", "INTEREST RATE", "BOE", "ECB", "SNB")
BLACKOUT_WINDOW = 30  # minutes


class NewsFilterPlugin(RulePluginInterface):
    def initialize(self, config: Dict[str, Any]) -> None:
        self._window = config.get("window_minutes", BLACKOUT_WINDOW)
        self._enabled = config.get("enabled", True)

    def evaluate(self, context: Dict[str, Any], facts: Dict[str, Any],
                 setup_result: Any = None, decision: Any = None) -> RuleResult:
        events = context.get("news_events") or []
        now = datetime.now(timezone.utc)
        window = timedelta(minutes=self._window)
        for ev in events:
            title = (ev.get("title", "") if isinstance(ev, dict) else str(ev)).upper()
            for kw in BLACKOUT_KEYWORDS:
                if kw in title:
                    ev_time = ev.get("time") or ev.get("timestamp") if isinstance(ev, dict) else None
                    if ev_time:
                        if isinstance(ev_time, (int, float)):
                            ev_time = datetime.fromtimestamp(ev_time, tz=timezone.utc)
                        if abs((ev_time - now).total_seconds()) < window.total_seconds():
                            return RuleResult("REJECT", f"News blackout: {kw}", priority=self.priority())
        return RuleResult("APPROVE", "No news blackout", priority=self.priority())

    def metadata(self) -> Dict[str, Any]:
        return {"name": "news_filter", "type": "risk", "version": "1.0"}

    def priority(self) -> int: return 10
    def enabled(self) -> bool: return getattr(self, "_enabled", True)
