"""ForexFactory Economic Calendar Adapter."""
import logging
import requests
from datetime import datetime
from typing import List, Dict

log = logging.getLogger(__name__)

class ForexFactoryCalendar:
    BASE_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    
    def fetch_events(self) -> List[Dict]:
        try:
            resp = requests.get(self.BASE_URL, timeout=10)
            resp.raise_for_status()
            events = resp.json()
            return [e for e in events if e.get('impact') == 'High']
        except Exception as e:
            log.error(f"ForexFactory fetch failed: {e}")
            return []
    
    def is_news_blackout(self, symbol: str = "USD") -> bool:
        try:
            events = self.fetch_events()
            if not events:
                # If API fails or no events, don't block
                return False
            
            now = datetime.utcnow()
            for event in events:
                if symbol.upper() not in event.get('country', ''):
                    continue
                
                event_time_str = event.get('date') or ""
                try:
                    event_time = datetime.fromisoformat(event_time_str.replace('Z', '+00:00'))
                    diff = abs((now - event_time).total_seconds() / 60)
                    
                    if diff <= 30:
                        log.warning(f"News blackout: {event.get('title')} at {event_time}")
                        return True
                except Exception:
                    pass
            
            return False
        except Exception:
            # Final fail-open
            return False
