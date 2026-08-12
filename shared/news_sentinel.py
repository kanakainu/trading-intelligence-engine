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
        self._cache = {}
        self._load_cache()

    def _load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    self._cache = json.load(f)
            except json.JSONDecodeError:
                self._cache = {}

    def _save_cache(self):
        with open(CACHE_FILE, 'w') as f:
            json.dump(self._cache, f, indent=2)

    def _parse_time(self, date_str, time_str):
        # Handle various date/time formats from ForexFactory
        # Example: "Mar 22, 2026" "08:30 AM"
        try:
            # Try parsing with AM/PM
            dt_obj = datetime.strptime(f"{date_str} {time_str}", "%b %d, %Y %I:%M %p")
        except ValueError:
            try:
                # Try parsing 24-hour format
                dt_obj = datetime.strptime(f"{date_str} {time_str}", "%b %d, %Y %H:%M")
            except ValueError:
                # Fallback to ISO format if date_str is already ISO
                return datetime.fromisoformat(date_str).astimezone(timezone.utc)


        # Assume local timezone if none specified, then convert to UTC
        # ForexFactory calendar is usually published in local time of the event
        # For simplicity, assume server timezone is WIB (UTC+7) or handle dynamically
        # For this cron, we will assume event times are already UTC or a known offset
        # A more robust solution would involve pytz or dateutil
        return dt_obj.replace(tzinfo=timezone.utc) # Assuming ff_calendar_thisweek.json provides UTC or can be treated as such for consistency

    def fetch_calendar(self):
        try:
            response = requests.get(FF_CALENDAR_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # The API response might be {"ts": <timestamp>, "events": [...]} or just [...]
            events = data.get("events", data) if isinstance(data, dict) else data
            
            self._cache["last_fetch_time"] = datetime.now(timezone.utc).isoformat()
            self._cache["events"] = events
            self._save_cache()
            return events
        except requests.exceptions.RequestException as e:
            print(f"Error fetching ForexFactory calendar: {e}. Attempting to use cache.")
            return self._cache.get("events", [])
        except json.JSONDecodeError:
            print("Error decoding JSON from ForexFactory calendar. Attempting to use cache.")
            return self._cache.get("events", [])

    def check_blackout(self):
        current_time_utc = datetime.now(timezone.utc)
        events = self.fetch_calendar()
        
        blackout_active = False
        reasons = []

        if not events and os.path.exists(BLACKOUT_STATUS_FILE):
            # Sticky blackout: if no new events and previous blackout was active, maintain it for a window
            try:
                with open(BLACKOUT_STATUS_FILE, 'r') as f:
                    last_status = json.load(f)
                last_checked_at_str = last_status.get("checked_at", "")
                if last_checked_at_str != "MANUAL_OVERRIDE_OFF":
                    last_checked_at = datetime.fromisoformat(last_checked_at_str)
                    if last_status.get("active", False) and \
                       (current_time_utc - last_checked_at) < timedelta(minutes=BLACKOUT_WINDOW_MINUTES * 2): # Double the window for stickiness
                        blackout_active = True
                        reasons.append(f"Sticky blackout: no new events, maintaining previous state from {last_checked_at_str}")
            except (json.JSONDecodeError, ValueError):
                pass # Ignore if file is corrupt or format changed

        for event in events:
            impact = event.get("impact", "").replace(" ", "").replace("(", "").replace(")", "").replace("-", "") # Normalize like "HighImpact"
            currency = event.get("currency", "").upper()
            
            if impact in HIGH_IMPACT_EVENTS and currency in ["USD", "ALL", "XAU"]: # Assuming XAU is also relevant for USD pair
                event_date = event.get("date") # e.g., "Mar 22, 2026"
                event_time = event.get("time") # e.g., "08:30 AM"

                if event_date and event_time:
                    try:
                        event_dt_utc = self._parse_time(event_date, event_time)
                        blackout_start = event_dt_utc - timedelta(minutes=BLACKOUT_WINDOW_MINUTES)
                        blackout_end = event_dt_utc + timedelta(minutes=BLACKOUT_WINDOW_MINUTES)

                        if blackout_start <= current_time_utc <= blackout_end:
                            blackout_active = True
                            reasons.append(f"High impact news for {currency} at {event_dt_utc.isoformat()} (Impact: {impact})")
                    except ValueError as e:
                        reasons.append(f"Failed to parse event time for {currency} event: {event_date} {event_time} - {e}")
                else:
                    reasons.append(f"Missing date/time for {currency} event (Impact: {impact})")

        status_data = {
            "active": blackout_active,
            "reasons": list(set(reasons)), # Unique reasons
            "checked_at": current_time_utc.isoformat()
        }

        with open(BLACKOUT_STATUS_FILE, 'w') as f:
            json.dump(status_data, f, indent=2)
        
        return status_data

if __name__ == "__main__":
    sentinel = NewsSentinel()
    status = sentinel.check_blackout()
    print(json.dumps(status, indent=2))
