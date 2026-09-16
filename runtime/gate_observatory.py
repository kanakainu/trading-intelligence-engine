"""Gate Observatory — Full observability for TIE V3 trading engine.

Logs every gate decision, tracks survival rates, generates reports.
NO trading logic changes. Only observability.
"""
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import sqlite3

logger = logging.getLogger("GateObservatory")

# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GateResult:
    gate_name: str
    status: str  # PASS, FAIL, SKIPPED
    current_value: Optional[float] = None
    threshold: Optional[float] = None
    reason: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class DecisionTrace:
    scan_id: str
    symbol: str
    strategy: str
    timestamp: str
    gates: List[GateResult] = field(default_factory=list)
    final_outcome: str = "NO_TRADE"  # NO_TRADE, SIGNAL_GENERATED, TRADE_EXECUTED
    rejection_reason: str = ""
    
    def add_gate(self, gate: GateResult):
        self.gates.append(gate)
    
    def to_dict(self) -> dict:
        return {
            "scan_id": self.scan_id,
            "symbol": self.symbol,
            "strategy": self.strategy,
            "timestamp": self.timestamp,
            "outcome": self.final_outcome,
            "rejection_reason": self.rejection_reason,
            "gates": [
                {
                    "gate": g.gate_name,
                    "status": g.status,
                    "value": g.current_value,
                    "threshold": g.threshold,
                    "reason": g.reason
                }
                for g in self.gates
            ]
        }


# ─────────────────────────────────────────────────────────────────────────────
# Gate Observatory — Main Class
# ─────────────────────────────────────────────────────────────────────────────

class GateObservatory:
    """Observability layer for TIE V3. Tracks every gate decision."""
    
    def __init__(self, db_path: str = "/home/ubuntu/trading-intelligence-engine/data/gate_observatory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
        # In-memory rolling stats (last 24h)
        self.stats = defaultdict(lambda: defaultdict(int))
        self.rejection_counts = defaultdict(int)
        self.strategy_stats = defaultdict(lambda: {"scans": 0, "passed": 0, "blocked": 0, "executed": 0})
        self.symbol_stats = defaultdict(lambda: {"scans": 0, "signals": 0, "trades": 0, "wins": 0, "losses": 0})
    
    def _init_db(self):
        """Initialize SQLite tables for persistent storage."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Gate decisions table
        c.execute("""
            CREATE TABLE IF NOT EXISTS gate_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT,
                symbol TEXT,
                strategy TEXT,
                gate_name TEXT,
                status TEXT,
                current_value REAL,
                threshold REAL,
                reason TEXT,
                timestamp TEXT
            )
        """)
        
        # Decision traces table
        c.execute("""
            CREATE TABLE IF NOT EXISTS decision_traces (
                scan_id TEXT PRIMARY KEY,
                symbol TEXT,
                strategy TEXT,
                outcome TEXT,
                rejection_reason TEXT,
                trace_json TEXT,
                timestamp TEXT
            )
        """)
        
        # Hourly reports table
        c.execute("""
            CREATE TABLE IF NOT EXISTS hourly_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hour TEXT,
                report_json TEXT,
                generated_at TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Logging Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def log_gate(self, trace: DecisionTrace, gate_name: str, status: str,
                 current_value: Optional[float] = None, threshold: Optional[float] = None,
                 reason: str = ""):
        """Log a gate decision."""
        gate = GateResult(
            gate_name=gate_name,
            status=status,
            current_value=current_value,
            threshold=threshold,
            reason=reason
        )
        trace.add_gate(gate)
        
        # Update rolling stats
        key = (trace.symbol, trace.strategy, gate_name)
        self.stats[key][status] += 1
        
        # Track rejections
        if status == "FAIL":
            self.rejection_counts[f"{gate_name}: {reason}"] += 1
        
        # Log to DB
        self._persist_gate(trace.scan_id, trace.symbol, trace.strategy, gate)
        
        logger.info(f"[{trace.symbol}/{trace.strategy}] Gate {gate_name}: {status} | {reason}")
    
    def finalize_trace(self, trace: DecisionTrace, outcome: str, rejection_reason: str = ""):
        """Finalize a decision trace."""
        trace.final_outcome = outcome
        trace.rejection_reason = rejection_reason
        
        # Update strategy stats
        self.strategy_stats[trace.strategy]["scans"] += 1
        if outcome == "SIGNAL_GENERATED":
            self.strategy_stats[trace.strategy]["passed"] += 1
        elif outcome == "NO_TRADE":
            self.strategy_stats[trace.strategy]["blocked"] += 1
        elif outcome == "TRADE_EXECUTED":
            self.strategy_stats[trace.strategy]["executed"] += 1
        
        # Update symbol stats
        self.symbol_stats[trace.symbol]["scans"] += 1
        if outcome == "SIGNAL_GENERATED":
            self.symbol_stats[trace.symbol]["signals"] += 1
        elif outcome == "TRADE_EXECUTED":
            self.symbol_stats[trace.symbol]["trades"] += 1
        
        # Persist trace
        self._persist_trace(trace)
        
        logger.debug(f"[{trace.symbol}/{trace.strategy}] Outcome: {outcome} | {rejection_reason}")
    
    def _persist_gate(self, scan_id: str, symbol: str, strategy: str, gate: GateResult):
        """Persist gate decision to SQLite."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO gate_decisions 
            (scan_id, symbol, strategy, gate_name, status, current_value, threshold, reason, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (scan_id, symbol, strategy, gate.gate_name, gate.status,
              gate.current_value, gate.threshold, gate.reason, gate.timestamp))
        conn.commit()
        conn.close()
    
    def _persist_trace(self, trace: DecisionTrace):
        """Persist decision trace to SQLite."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO decision_traces
            (scan_id, symbol, strategy, outcome, rejection_reason, trace_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (trace.scan_id, trace.symbol, trace.strategy, trace.final_outcome,
              trace.rejection_reason, json.dumps(trace.to_dict()), trace.timestamp))
        conn.commit()
        conn.close()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Reports
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_gate_survival_analytics(self, symbol: str = None, strategy: str = None) -> dict:
        """Get PASS/FAIL rates per gate."""
        result = {}
        for (sym, strat, gate), counts in self.stats.items():
            if symbol and sym != symbol:
                continue
            if strategy and strat != strategy:
                continue
            
            total = sum(counts.values())
            pass_rate = counts["PASS"] / total * 100 if total > 0 else 0
            
            key = f"{sym}/{strat}/{gate}"
            result[key] = {
                "PASS": counts["PASS"],
                "FAIL": counts["FAIL"],
                "SKIPPED": counts["SKIPPED"],
                "pass_rate": round(pass_rate, 1)
            }
        return result
    
    def get_top_rejections(self, limit: int = 10) -> List[dict]:
        """Get top rejection reasons."""
        sorted_rejections = sorted(self.rejection_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        return [{"reason": r, "count": c} for r, c in sorted_rejections]
    
    def get_strategy_scoreboard(self) -> dict:
        """Get per-strategy stats."""
        return dict(self.strategy_stats)
    
    def get_symbol_scoreboard(self) -> dict:
        """Get per-symbol stats."""
        return dict(self.symbol_stats)
    
    def generate_heatmap(self) -> dict:
        """Generate gate PASS percentage heatmap."""
        gates = ["Liquidity", "Session", "Regime", "Opportunity", "Detector", 
                 "Confidence", "Planner", "Risk", "Entry", "Execution"]
        strategies = ["Bystra", "Aggressive", "SemiHFT"]
        
        heatmap = {}
        for strat in strategies:
            heatmap[strat] = {}
            for gate in gates:
                key = (strat, gate)
                # Aggregate across symbols
                total_pass = 0
                total_count = 0
                for (sym, s, g), counts in self.stats.items():
                    if s == strat and g == gate:
                        total_pass += counts.get("PASS", 0)
                        total_count += counts.get("PASS", 0) + counts.get("FAIL", 0)
                
                pass_rate = total_pass / total_count * 100 if total_count > 0 else 0
                heatmap[strat][gate] = round(pass_rate, 1)
        
        return heatmap
    
    def generate_hourly_report(self) -> dict:
        """Generate hourly rejection report."""
        now = datetime.now(timezone.utc)
        hour = now.strftime("%Y-%m-%d %H:00")
        
        report = {
            "hour": hour,
            "gate_survival": self.get_gate_survival_analytics(),
            "top_rejections": self.get_top_rejections(),
            "strategy_scoreboard": self.get_strategy_scoreboard(),
            "symbol_scoreboard": self.get_symbol_scoreboard(),
            "heatmap": self.generate_heatmap()
        }
        
        # Persist report
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO hourly_reports (hour, report_json, generated_at)
            VALUES (?, ?, ?)
        """, (hour, json.dumps(report), now.isoformat()))
        conn.commit()
        conn.close()
        
        logger.info(f"Generated hourly report for {hour}")
        return report
    
    def generate_daily_summary(self) -> dict:
        """Generate daily summary report."""
        now = datetime.now(timezone.utc)
        date = now.strftime("%Y-%m-%d")
        
        summary = {
            "date": date,
            "total_scans": sum(s["scans"] for s in self.strategy_stats.values()),
            "total_signals": sum(s["signals"] for s in self.symbol_stats.values()),
            "total_trades": sum(s["trades"] for s in self.symbol_stats.values()),
            "strategy_breakdown": self.get_strategy_scoreboard(),
            "symbol_breakdown": self.get_symbol_scoreboard(),
            "top_rejections": self.get_top_rejections(20),
            "heatmap": self.generate_heatmap()
        }
        
        logger.info(f"Generated daily summary for {date}")
        return summary
    
    def export_to_json(self, path: Optional[str] = None):
        """Export current stats to JSON."""
        if path is None:
            path = f"/home/ubuntu/tie-dashboard/data/gate_observatory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        data = {
            "gate_survival": self.get_gate_survival_analytics(),
            "top_rejections": self.get_top_rejections(),
            "strategy_scoreboard": self.get_strategy_scoreboard(),
            "symbol_scoreboard": self.get_symbol_scoreboard(),
            "heatmap": self.generate_heatmap(),
            "daily_summary": self.generate_daily_summary()
        }
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Exported observatory data to {path}")
        return path


# ─────────────────────────────────────────────────────────────────────────────
# Singleton Instance
# ─────────────────────────────────────────────────────────────────────────────

_observatory = None

def get_observatory() -> GateObservatory:
    """Get singleton observatory instance."""
    global _observatory
    if _observatory is None:
        _observatory = GateObservatory()
    return _observatory


# ─────────────────────────────────────────────────────────────────────────────
# Integration Helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_trace(scan_id: str, symbol: str, strategy: str) -> DecisionTrace:
    """Create a new decision trace."""
    return DecisionTrace(
        scan_id=scan_id,
        symbol=symbol,
        strategy=strategy,
        timestamp=datetime.now(timezone.utc).isoformat()
    )
