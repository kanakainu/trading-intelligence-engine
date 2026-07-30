"""HCK Dashboard Wire — Sends TIE events to Hermes Cognitive Kernel for visualization."""
import os, json, logging
from datetime import datetime, timezone

HCK_LOG_PATH = "/home/ubuntu/trading-intelligence-engine/logs/hck_events.jsonl"

def log_to_hck(event_type: str, data: dict):
    """Append event to HCK log file."""
    os.makedirs(os.path.dirname(HCK_LOG_PATH), exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        "data": data
    }
    with open(HCK_LOG_PATH, "a") as f:
        f.write(json.dumps(payload) + "\n")

def push_decision(decision):
    log_to_hck("STRATEGY_DECISION", {
        "setup": decision.setup_name,
        "action": decision.action,
        "confidence": decision.confidence,
        "explanation": decision.explanation
    })

def push_trade(result):
    log_to_hck("TRADE_EXECUTION", result)
