import asyncio
import httpx
import logging
import json
import os
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

logger = logging.getLogger("news_sentinel")

def check_news_blackout() -> tuple[bool, str]:
    """Module-level helper: check if a news blackout is active."""
    path = "/tmp/tie_news_blackout.json"
    if not os.path.exists(path):
        return False, ""
    try:
        with open(path, "r") as f:
            data = json.load(f)
            if data.get("active"):
                return True, "; ".join(data.get("reasons", []))
    except:
        pass
    return False, ""


class NewsSentinel:
    """
    Adopted from Nexus Trading System.
    Handles economic calendar parsing and news blackout detection for TIE V4.
    """
    FF_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    BLACKOUT_FILE = "/tmp/tie_news_blackout.json"
    BLACKOUT_MINUTES = 30

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=20.0)

    async def fetch_calendar(self):
        """Fetch this week's economic calendar."""
        try:
            resp = await self.client.get(self.FF_CALENDAR_URL)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch calendar: {e}")
            return []

    def classify_impact(self, event):
        """Classify event impact as HIGH, MEDIUM, or LOW."""
        impact = event.get("impact", "").lower()
        if "high" in impact:
            return "HIGH"
        if "medium" in impact:
            return "MEDIUM"
        return "LOW"

    # Currencies that move XAUUSD. AUD/CAD/NZD/CHF/etc skipped.
    XAU_RELEVANT_CURRENCIES = {"USD", "ALL"}  # ALL = global events (Fed, World Bank)
    XAU_RELEVANT_KEYWORDS = {
        "fed", "fomc", "powell", "inflation", "cpi", "pce", "nfp",
        "non-farm", "unemployment", "gdp", "interest rate", "treasury",
        "debt", "dollar", "dxy", "reserve", "yield"
    }

    async def check_blackout(self):
        """Check if we are currently in a news blackout window."""
        events = await self.fetch_calendar()
        now = datetime.now(timezone.utc)
        
        blackout_active = False
        reasons = []
        
        for event in events:
            if self.classify_impact(event) != "HIGH":
                continue

            # XAU-relevant filter: only USD events or XAU-moving keywords
            country = (event.get("country") or "").upper()
            title_lower = (event.get("title") or "").lower()
            is_relevant = (
                country in self.XAU_RELEVANT_CURRENCIES
                or any(kw in title_lower for kw in self.XAU_RELEVANT_KEYWORDS)
            )
            if not is_relevant:
                continue
                
            # Parse timestamp (ForexFactory format usually ISO or similar)
            try:
                # Expected: "2026-08-07T00:00:00-04:00"
                ev_time = datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
                if ev_time.tzinfo is None:
                    ev_time = ev_time.replace(tzinfo=timezone.utc)
            except:
                continue

            # Check window ±30 mins
            diff = abs((ev_time - now).total_seconds()) / 60
            if diff <= self.BLACKOUT_MINUTES:
                blackout_active = True
                reasons.append(f"{event.get('title')} ({event.get('country')}) at {ev_time.isoformat()}")

        result = {
            "active": blackout_active,
            "reasons": reasons,
            "checked_at": now.isoformat()
        }
        
        with open(self.BLACKOUT_FILE, "w") as f:
            json.dump(result, f)
            
        return result

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sentinel = NewsSentinel()
    loop = asyncio.get_event_loop()
    res = loop.run_until_complete(sentinel.check_blackout())
    print(json.dumps(res, indent=2))
