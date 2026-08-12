import json
import requests
from datetime import datetime, timedelta, timezone
import os
import time

# --- Constants ---
FF_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
BLACKOUT_WINDOW_MINUTES = 30  # +/- minutes around high impact news
HIGH_IMPACT_EVENTS = ["High"]
CACHE_FILE = "/tmp/ff_calendar_cache.json"
BLACKOUT_STATUS_FILE = "/tmp/tie_news_blackout.json"

class NewsSentinel:
    def __init__(self):
        self._cache = {"events": []}
        self._load_cache()

    def _load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._cache = data
                    else:
                        self._cache = {"events": data}
            except json.JSONDecodeError:
                self._cache = {"events": []}

    def _save_cache(self):
        with open(CACHE_FILE, 'w') as f:
            json.dump(self._cache, f, indent=2)

    def _parse_time(self, date_str, time_str=None):
        # Handle "YYYY-MM-DDTHH:MM:SSZ" format from cache/ForexFactory
        if "T" in date_str:
            try:
                # Replace Z with +00:00 for fromisoformat compatibility in some python versions
                clean_date = date_str.replace("Z", "+00:00")
                return datetime.fromisoformat(clean_date).astimezone(timezone.utc)
            except ValueError:
                pass

        if not time_str:
             try:
                return datetime.fromisoformat(date_str).astimezone(timezone.utc)
             except ValueError:
                raise ValueError(f"Missing time_str and date_str not ISO: {date_str}")

        try:
            dt_obj = datetime.strptime(f"{date_str} {time_str}", "%b %d, %Y %I:%M %p")
        except ValueError:
            try:
                dt_obj = datetime.strptime(f"{date_str} {time_str}", "%b %d, %Y %H:%M")
            except ValueError:
                try:
                    return datetime.strptime(date_str, "%b %d, %Y").replace(tzinfo=timezone.utc)
                except ValueError:
                    raise ValueError(f"Unknown date/time format: {date_str} {time_str}")

        return dt_obj.replace(tzinfo=timezone.utc)

    def fetch_calendar(self):
        try:
            response = requests.get(FF_CALENDAR_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            events = data.get("events", data) if isinstance(data, dict) else data
            
            self._cache["last_fetch_time"] = datetime.now(timezone.utc).isoformat()
            self._cache["events"] = events
            self._save_cache()
            return events
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            print(f"Fetch failed: {e}. Using cache.")
            return self._cache.get("events", [])

    def check_blackout(self):
        current_time_utc = datetime.now(timezone.utc)
        events = self.fetch_calendar()
        
        blackout_active = False
        reasons = []

        for event in events:
            impact = event.get("impact", "")
            currency = (event.get("currency") or event.get("country", "")).upper()
            
            if impact in HIGH_IMPACT_EVENTS and currency in ["USD", "ALL"]:
                event_date = event.get("date")
                event_time = event.get("time")

                try:
                    event_dt_utc = self._parse_time(event_date, event_time)
                    blackout_start = event_dt_utc - timedelta(minutes=BLACKOUT_WINDOW_MINUTES)
                    blackout_end = event_dt_utc + timedelta(minutes=BLACKOUT_WINDOW_MINUTES)

                    if blackout_start <= current_time_utc <= blackout_end:
                        blackout_active = True
                        reasons.append(f"High impact news for {currency} at {event_dt_utc.isoformat()} (Impact: {impact})")
                except ValueError:
                    continue

        status_data = {
            "active": blackout_active,
            "reasons": list(set(reasons)),
            "checked_at": current_time_utc.isoformat()
        }

        with open(BLACKOUT_STATUS_FILE, 'w') as f:
            json.dump(status_data, f, indent=2)
        
        return status_data

if __name__ == "__main__":
    sentinel = NewsSentinel()
    status = sentinel.check_blackout()
    print(json.dumps(status, indent=2))
