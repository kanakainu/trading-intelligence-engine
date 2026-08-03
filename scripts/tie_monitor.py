#!/usr/bin/env python3
"""TIE V3 Live Monitor — Push setup to Telegram."""
import json
import os
import sys
from datetime import datetime, timezone

STATUS_FILE = "/home/ubuntu/tie-dashboard/data/tie_status.json"

def main():
    if not os.path.exists(STATUS_FILE):
        print("No status file")
        return
    
    with open(STATUS_FILE) as f:
        data = json.load(f)
    
    pairs = data.get("pairs", {})
    ts = data.get("ts", "")
    
    lines = [f"⏱ TIE Monitor {ts.split('T')[0]} {ts.split('T')[1][:5]} — equity ${data.get('equity', 0):.2f}", ""]
    
    for sym, info in pairs.items():
        setup = info.get("setup")
        if setup:
            strategy = setup.get("strategy", "?")
            direction = setup.get("direction", "?")
            conf = setup.get("confidence", 0)
            entry = setup.get("entry", 0)
            sl = setup.get("sl", 0)
            tp = setup.get("tp", 0)
            rr = setup.get("risk_reward", 0)
            
            lines.append(f"🎯 SETUP {sym} {direction} {entry:.2f}")
            lines.append(f"   conf={conf}% SL={sl:.2f} TP={tp:.2f} RR={rr:.2f}")
    
    if len(lines) == 2:
        lines.append("No active setup")
    
    print("\n".join(lines))

if __name__ == "__main__":
    main()
