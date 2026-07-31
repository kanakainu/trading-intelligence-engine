"""NewsFilterPlugin — REJECT if active news blackout window (real ForexFactory data)."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from core.rules.plugins.plugin_interface import RulePluginInterface, RuleResult

BLACKOUT_WINDOW = 30  # minutes


class NewsFilterPlugin(RulePluginInterface):
    def initialize(self, config: Dict[str, Any]) -> None:
        self._window = config.get("window_minutes", BLACKOUT_WINDOW)
        self._enabled = config.get("enabled", True)
        self._fetched = False

    def evaluate(self, context: Dict[str, Any], facts: Dict[str, Any],
                 setup_result: Any = None, decision: Any = None) -> RuleResult:
        if not self._enabled:
            return RuleResult("APPROVE", "News filter disabled", priority=self.priority())

        # Fetch real events from Investing (ForexFactory backup)
        try:
            from adapters.calendar.investing import InvestingCalendar
            calendar = InvestingCalendar()
            if calendar.is_news_blackout(symbol="USD"):
                return RuleResult("REJECT", "News blackout (30 min window, Investing)", priority=self.priority())
        except Exception as e:
            # Fallback: check events in context
            events = context.get("news_events") or []
            now = datetime.now(timezone.utc)
            window = timedelta(minutes=self._window)
            for ev in events:
                ev_time = ev.get("time") if isinstance(ev, dict) else None
                if ev_time:
                    if isinstance(ev_time, (int, float)):
                        ev_time = datetime.fromtimestamp(ev_time, tz=timezone.utc)
                    if abs((ev_time - now).total_seconds()) < window.total_seconds():
                        title = ev.get("title", "news") if isinstance(ev, dict) else "news"
                        return RuleResult("REJECT", f"News blackout: {title}", priority=self.priority())

        return RuleResult("APPROVE", "No news blackout", priority=self.priority())

    def metadata(self) -> Dict[str, Any]:
        return {"name": "news_filter", "type": "risk", "version": "1.0"}

    def priority(self) -> int: return 10
    def enabled(self) -> bool: return getattr(self, "_enabled", True)
