"""NewsFilterPlugin — REJECT if active news blackout window (ForexFactory data)."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from core.rules.plugins.plugin_interface import RulePluginInterface, RuleResult

BLACKOUT_WINDOW = 30  # minutes
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
HIGH_IMPACT = {"High"}  # only block on High impact USD/XAU news


class NewsFilterPlugin(RulePluginInterface):
    def initialize(self, config: Dict[str, Any]) -> None:
        self._window = config.get("window_minutes", BLACKOUT_WINDOW)
        self._enabled = config.get("enabled", True)
        self._events = []
        self._last_fetch = 0.0

    def _fetch_events(self):
        """Fetch FF calendar (cached 1h)."""
        import time, urllib.request, json
        if time.time() - self._last_fetch < 3600:
            return
        try:
            with urllib.request.urlopen(FF_URL, timeout=5) as r:
                self._events = json.loads(r.read())
            self._last_fetch = time.time()
        except Exception:
            pass  # keep stale cache on error

    def evaluate(self, context: Dict[str, Any], facts: Dict[str, Any],
                 setup_result: Any = None, decision: Any = None) -> RuleResult:
        if not self._enabled:
            return RuleResult("APPROVE", "News filter disabled", priority=self.priority())

        self._fetch_events()
        now = datetime.now(timezone.utc)
        window = timedelta(minutes=self._window)

        for ev in self._events:
            if ev.get("impact") not in HIGH_IMPACT:
                continue
            if ev.get("country") not in ("USD", "XAU", "All"):
                continue
            try:
                ev_time = datetime.fromisoformat(ev["date"])
                if ev_time.tzinfo is None:
                    ev_time = ev_time.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if abs((ev_time - now).total_seconds()) < window.total_seconds():
                return RuleResult("REJECT", f"News blackout: {ev.get('title','news')}", priority=self.priority())

        return RuleResult("APPROVE", "No news blackout", priority=self.priority())

    def metadata(self) -> Dict[str, Any]:
        return {"name": "news_filter", "type": "risk", "version": "2.0"}

    def priority(self) -> int: return 10
    def enabled(self) -> bool: return getattr(self, "_enabled", True)
