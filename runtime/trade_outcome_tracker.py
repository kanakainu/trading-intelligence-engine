#!/usr/bin/env python3
"""Trade outcome tracker — monitors MT5 positions, logs win/loss.
Updates /tmp/tie_wins.json when positions close.
Run: python3 runtime/trade_outcome_tracker.py &
"""
import json, time, urllib.request, ssl
from pathlib import Path

GATEWAY = "https://chips-extension-extensions-wearing.trycloudflare.com"
TOKEN = "Jojo_56790@_000tUi_OO9"
WINS_FILE = Path("/home/ubuntu/trading-intelligence-engine/data/tie_wins.json")
STATE_FILE = Path("/home/ubuntu/trading-intelligence-engine/data/tie_tracker_state.json")
CHECK_INTERVAL = 15  # seconds

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def api(path):
    req = urllib.request.Request(f"{GATEWAY}{path}",
        headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
        return json.loads(r.read())

def load_json(p, default):
    try:
        with open(p) as f: return json.load(f)
    except: return default

def save_json(p, data):
    with open(p, "w") as f: json.dump(data, f, indent=2)

def main():
    print("Trade outcome tracker started")
    while True:
        try:
            positions = api("/account/positions")
            current_tickets = {str(p["ticket"]): p for p in positions}
            
            # Load previous state
            prev_tickets = load_json(STATE_FILE, {})
            wins_data = load_json(WINS_FILE, {"wins": 0, "losses": 0})
            
            # Detect closed positions
            for ticket, info in prev_tickets.items():
                if ticket not in current_tickets:
                    # Position closed — check last known profit
                    last_profit = info.get("profit", 0)
                    if last_profit > 0:
                        wins_data["wins"] += 1
                        print(f"WIN  #{ticket} ${last_profit:.2f}")
                    elif last_profit < 0:
                        wins_data["losses"] += 1
                        print(f"LOSS #{ticket} ${last_profit:.2f}")
                    else:
                        # Closed at breakeven or unknown — count as win (BE locked)
                        wins_data["wins"] += 1
                        print(f"BE   #{ticket} $0.00")
            
            # Update current positions with profit
            new_state = {}
            for ticket, pos in current_tickets.items():
                new_state[ticket] = {
                    "direction": pos.get("direction", ""),
                    "profit": pos.get("profit", 0),
                    "entry": pos.get("price_open", 0),
                }
            
            save_json(STATE_FILE, new_state)
            save_json(WINS_FILE, wins_data)
            
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
