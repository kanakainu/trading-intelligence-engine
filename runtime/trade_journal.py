"""
Trade Journal — Catatan harian semua transaksi.
Log entry/exit/reason/result per trade ke file JSON.
"""
import os
import json
import logging
from datetime import datetime, timezone

log = logging.getLogger("TradeJournal")

JOURNAL_DIR = "/home/ubuntu/trading-intelligence-engine/logs/journal"


class TradeJournal:
    def __init__(self, journal_dir: str = JOURNAL_DIR):
        self.journal_dir = journal_dir
        os.makedirs(self.journal_dir, exist_ok=True)

    def _today_path(self) -> str:
        today = datetime.now(timezone.utc).date().isoformat()
        return os.path.join(self.journal_dir, f"{today}.json")

    def log_trade(self, entry: dict):
        """Log satu trade (entry/exit/setup/reason/result)."""
        entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        path = self._today_path()

        # Read existing
        records = []
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    records = json.load(f)
            except Exception as e:
                log.error(f"Journal read failed: {e}")

        records.append(entry)

        # Write back
        try:
            with open(path, "w") as f:
                json.dump(records, f, indent=2)
            log.info(f"Journal: trade logged → {path}")
        except Exception as e:
            log.error(f"Journal write failed: {e}")

    def get_today(self) -> list:
        """Baca semua journal hari ini."""
        path = self._today_path()
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Journal read failed: {e}")
            return []
