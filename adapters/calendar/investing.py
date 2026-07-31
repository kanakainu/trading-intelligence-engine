"""Investing.com Economic Calendar Adapter — Fail-Open Scraper."""
import logging
import requests
from datetime import datetime, timedelta
from typing import List, Dict
import re

log = logging.getLogger(__name__)


class InvestingCalendar:
    """Scrape economic calendar from Investing.com.
    
    Uses their public API endpoint. If it fails, returns empty (fail-open).
    """
    
    BASE_URL = "https://api.investing.com/api/financialdata/economiccalendar"
    
    # Country codes for USD
    USD_COUNTRIES = {"united states", "us", "usa", "america"}
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://www.investing.com",
            "Referer": "https://www.investing.com/economic-calendar/",
        })
    
    def fetch_events(self, days_ahead: int = 7) -> List[Dict]:
        """Fetch high-impact USD events from Investing calendar."""
        try:
            # Calculate date range
            now = datetime.utcnow()
            from_date = now.strftime("%Y-%m-%d")
            to_date = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
            
            params = {
                "fromDate": from_date,
                "toDate": to_date,
                "countries": "5",  # US country code in Investing
                "importance": "3",  # High impact only
                "timeZone": "UTC",
            }
            
            resp = self.session.get(self.BASE_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            events = data.get("data", [])
            filtered = []
            
            for e in events:
                try:
                    # Parse event time
                    event_time_str = e.get("date", "")
                    # Format: "Jul 31, 2025 12:30"
                    event_time = datetime.strptime(event_time_str, "%b %d, %Y %H:%M")
                    
                    country = e.get("country", "").lower()
                    if country not in self.USD_COUNTRIES:
                        continue
                    
                    importance = e.get("importance", 0)
                    if importance < 3:  # Only High impact
                        continue
                    
                    filtered.append({
                        "title": e.get("event", "Economic Event"),
                        "time": event_time,
                        "country": country,
                        "actual": e.get("actual"),
                        "forecast": e.get("forecast"),
                        "previous": e.get("previous"),
                        "importance": importance,
                    })
                except Exception as parse_err:
                    log.debug(f"Failed to parse event: {parse_err}")
                    continue
            
            log.info(f"InvestingCalendar: fetched {len(filtered)} high-impact USD events")
            return filtered
            
        except Exception as e:
            log.warning(f"InvestingCalendar fetch failed (fail-open): {e}")
            return []
    
    def is_news_blackout(self, symbol: str = "USD", window_minutes: int = 30) -> bool:
        """Check if any high-impact USD news within window_minutes.
        
        Fail-open: if fetch fails, return False (don't block).
        """
        try:
            events = self.fetch_events()
            if not events:
                return False  # No events or fetch failed -> no blackout
            
            now = datetime.utcnow()
            window = timedelta(minutes=window_minutes)
            
            for event in events:
                event_time = event.get("time")
                if not event_time:
                    continue
                
                diff = abs((event_time - now).total_seconds())
                if diff <= window.total_seconds():
                    log.warning(f"News blackout: {event['title']} at {event_time} (diff={diff/60:.1f}min)")
                    return True
            
            return False
            
        except Exception as e:
            log.warning(f"InvestingCalendar blackout check failed (fail-open): {e}")
            return False


# Backward compatibility alias
ForexFactoryCalendar = InvestingCalendar