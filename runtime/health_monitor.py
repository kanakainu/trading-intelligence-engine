"""Health Monitoring — runtime metrics dashboard.

Gateway delay, memory, CPU, tick freeze, reconnect count.

NO trading logic. Pure observability.
"""
import time
import psutil
import sqlite3
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timezone

log = logging.getLogger("HealthMonitor")

DB_PATH = "/home/ubuntu/trading-intelligence-engine/data/health_metrics.db"


@dataclass
class HealthMetric:
    ts: float
    metric_name: str
    value: float
    unit: str
    status: str  # OK, WARN, CRITICAL


class HealthMonitor:
    """Track runtime health metrics.

    Job:
    - Gateway latency (ping)
    - Memory usage (%)
    - CPU usage (%)
    - Tick freeze (seconds since last tick)
    - Reconnect count
    """

    def __init__(self, gateway_url: str = None):
        self.gateway_url = gateway_url
        self._last_tick = time.time()
        self._reconnect_count = 0
        self._conn = sqlite3.connect(DB_PATH, timeout=5)
        self._ensure_table()

    def _ensure_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS health_metrics (
                ts REAL,
                metric_name TEXT,
                value REAL,
                unit TEXT,
                status TEXT
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_health_ts ON health_metrics(ts)")
        self._conn.commit()

    def record_tick(self):
        """Call every scan to track tick freshness."""
        self._last_tick = time.time()

    def record_reconnect(self):
        """Call when gateway reconnects."""
        self._reconnect_count += 1
        log.warning(f"Gateway reconnect count: {self._reconnect_count}")

    def check_gateway_latency(self) -> HealthMetric:
        """Ping gateway and record latency."""
        import requests
        start = time.time()
        status = "OK"
        try:
            if self.gateway_url:
                resp = requests.get(f"{self.gateway_url}/health", timeout=5)
                latency_ms = (time.time() - start) * 1000
                if latency_ms > 500:
                    status = "WARN"
                if latency_ms > 2000:
                    status = "CRITICAL"
            else:
                latency_ms = 0
        except Exception as e:
            latency_ms = 9999
            status = "CRITICAL"
            log.error(f"Gateway ping failed: {e}")

        return self._record("gateway_latency_ms", latency_ms, "ms", status)

    def check_memory(self) -> HealthMetric:
        """Check memory usage."""
        mem = psutil.virtual_memory()
        percent = mem.percent
        status = "OK"
        if percent > 80:
            status = "WARN"
        if percent > 95:
            status = "CRITICAL"
        return self._record("memory_percent", percent, "%", status)

    def check_cpu(self) -> HealthMetric:
        """Check CPU usage."""
        percent = psutil.cpu_percent(interval=1)
        status = "OK"
        if percent > 80:
            status = "WARN"
        if percent > 95:
            status = "CRITICAL"
        return self._record("cpu_percent", percent, "%", status)

    def check_tick_freeze(self) -> HealthMetric:
        """Check seconds since last tick."""
        freeze_secs = time.time() - self._last_tick
        status = "OK"
        if freeze_secs > 30:
            status = "WARN"
        if freeze_secs > 60:
            status = "CRITICAL"
        return self._record("tick_freeze_secs", freeze_secs, "s", status)

    def check_reconnect_count(self) -> HealthMetric:
        """Check reconnect count today."""
        status = "OK"
        if self._reconnect_count > 3:
            status = "WARN"
        if self._reconnect_count > 10:
            status = "CRITICAL"
        return self._record("reconnect_count", self._reconnect_count, "count", status)

    def _record(self, name: str, value: float, unit: str, status: str) -> HealthMetric:
        m = HealthMetric(
            ts=time.time(),
            metric_name=name,
            value=value,
            unit=unit,
            status=status
        )
        self._conn.execute(
            "INSERT INTO health_metrics(ts, metric_name, value, unit, status) VALUES (?,?,?,?,?)",
            (m.ts, m.metric_name, m.value, m.unit, m.status)
        )
        self._conn.commit()
        if status != "OK":
            log.warning(f"Health: {name}={value}{unit} [{status}]")
        return m

    def run_all_checks(self) -> Dict[str, HealthMetric]:
        """Run all health checks."""
        return {
            "gateway_latency": self.check_gateway_latency(),
            "memory": self.check_memory(),
            "cpu": self.check_cpu(),
            "tick_freeze": self.check_tick_freeze(),
            "reconnect_count": self.check_reconnect_count(),
        }

    def get_status(self) -> dict:
        """Return current health summary."""
        checks = self.run_all_checks()
        criticals = [k for k, v in checks.items() if v.status == "CRITICAL"]
        warns = [k for k, v in checks.items() if v.status == "WARN"]
        return {
            "status": "CRITICAL" if criticals else ("WARN" if warns else "OK"),
            "criticals": criticals,
            "warnings": warns,
            "metrics": {k: {"value": v.value, "unit": v.unit, "status": v.status} for k, v in checks.items()},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
