"""Monte Carlo Replay Engine — replay historical data through TIE V3 pipeline.

Count gate passes/fails to identify bottlenecks.
NO live trading. Only simulation.
"""
import json
import logging
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import uuid

logger = logging.getLogger("MonteCarloReplay")

# ─────────────────────────────────────────────────────────────────────────────
# Gate Statistics
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GateStats:
    """Statistics for a single gate."""
    name: str
    pass_count: int = 0
    fail_count: int = 0
    skip_count: int = 0
    
    @property
    def total(self) -> int:
        return self.pass_count + self.fail_count + self.skip_count
    
    @property
    def pass_rate(self) -> float:
        return (self.pass_count / self.total * 100) if self.total > 0 else 0.0


@dataclass
class ReplayResult:
    """Result of a single replay scan."""
    scan_id: str
    symbol: str
    timestamp: str
    strategy: str
    gates: Dict[str, GateStats] = field(default_factory=dict)
    signal_generated: bool = False
    trade_executed: bool = False
    rejection_reason: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Monte Carlo Replay Engine
# ─────────────────────────────────────────────────────────────────────────────

class MonteCarloReplay:
    """Replay historical data through TIE V3 pipeline."""
    
    def __init__(self, db_path: str = "/home/ubuntu/trading-intelligence-engine/data/monte_carlo_replay.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
        # Gate stats aggregated
        self.gate_stats: Dict[str, GateStats] = defaultdict(lambda: GateStats(name="unknown"))
        self.scan_count = 0
        self.signal_count = 0
        self.trade_count = 0
        
    def _init_db(self):
        """Initialize SQLite tables."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS replay_results (
                scan_id TEXT PRIMARY KEY,
                symbol TEXT,
                timestamp TEXT,
                strategy TEXT,
                signal_generated INTEGER,
                trade_executed INTEGER,
                rejection_reason TEXT,
                gates_json TEXT
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS gate_stats (
                gate_name TEXT PRIMARY KEY,
                pass_count INTEGER,
                fail_count INTEGER,
                skip_count INTEGER
            )
        """)
        
        conn.commit()
        conn.close()
    
    def record_gate(self, gate_name: str, status: str):
        """Record a gate decision."""
        if gate_name not in self.gate_stats:
            self.gate_stats[gate_name] = GateStats(name=gate_name)
        
        if status == "PASS":
            self.gate_stats[gate_name].pass_count += 1
        elif status == "FAIL":
            self.gate_stats[gate_name].fail_count += 1
        else:
            self.gate_stats[gate_name].skip_count += 1
    
    def record_scan(self, result: ReplayResult):
        """Record a scan result."""
        self.scan_count += 1
        if result.signal_generated:
            self.signal_count += 1
        if result.trade_executed:
            self.trade_count += 1
        
        # Persist
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO replay_results
            (scan_id, symbol, timestamp, strategy, signal_generated, trade_executed, rejection_reason, gates_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (result.scan_id, result.symbol, result.timestamp, result.strategy,
              int(result.signal_generated), int(result.trade_executed),
              result.rejection_reason, json.dumps({k: {"pass": v.pass_count, "fail": v.fail_count, "skip": v.skip_count} for k, v in result.gates.items()})))
        conn.commit()
        conn.close()
    
    def get_summary(self) -> dict:
        """Get replay summary statistics."""
        return {
            "total_scans": self.scan_count,
            "signals_generated": self.signal_count,
            "trades_executed": self.trade_count,
            "signal_rate": (self.signal_count / self.scan_count * 100) if self.scan_count > 0 else 0.0,
            "trade_rate": (self.trade_count / self.scan_count * 100) if self.scan_count > 0 else 0.0,
            "gate_stats": {
                name: {
                    "PASS": stats.pass_count,
                    "FAIL": stats.fail_count,
                    "SKIPPED": stats.skip_count,
                    "pass_rate": round(stats.pass_rate, 2)
                }
                for name, stats in self.gate_stats.items()
            }
        }
    
    def generate_report(self) -> str:
        """Generate human-readable report."""
        summary = self.get_summary()
        
        lines = [
            "=" * 60,
            "MONTE CARLO REPLAY REPORT",
            "=" * 60,
            "",
            f"Total Scans:              {summary['total_scans']:,}",
            f"Signals Generated:        {summary['signals_generated']:,}",
            f"Trades Executed:          {summary['trades_executed']:,}",
            f"Signal Rate:              {summary['signal_rate']:.2f}%",
            f"Trade Rate:               {summary['trade_rate']:.2f}%",
            "",
            "-" * 60,
            "GATE STATISTICS",
            "-" * 60,
            "",
        ]
        
        # Sort by pass rate ascending (bottlenecks first)
        sorted_gates = sorted(
            summary["gate_stats"].items(),
            key=lambda x: x[1]["pass_rate"]
        )
        
        for gate_name, stats in sorted_gates:
            lines.append(
                f"{gate_name:30} | PASS: {stats['PASS']:>6} | FAIL: {stats['FAIL']:>6} | "
                f"SKIP: {stats['SKIPPED']:>6} | Rate: {stats['pass_rate']:>6.2f}%"
            )
        
        lines.extend([
            "",
            "=" * 60,
            "BOTTLENECK ANALYSIS",
            "=" * 60,
            "",
        ])
        
        # Identify bottlenecks
        bottlenecks = [
            (name, stats) for name, stats in sorted_gates
            if stats["pass_rate"] < 50.0 and stats["PASS"] + stats["FAIL"] > 0
        ]
        
        if bottlenecks:
            lines.append("Top Bottlenecks (pass rate < 50%):")
            for name, stats in bottlenecks[:5]:
                lines.append(f"  • {name}: {stats['pass_rate']:.2f}% pass rate")
        else:
            lines.append("No critical bottlenecks detected.")
        
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Historical Data Loader (Stub - requires MT5 connection)
# ─────────────────────────────────────────────────────────────────────────────

class HistoricalDataLoader:
    """Load historical candle data for replay."""
    
    def __init__(self, mt5_gateway_url: str = "http://127.0.0.1:5000"):
        self.mt5_gateway_url = mt5_gateway_url
    
    def load_candles(self, symbol: str, timeframe: str, days: int = 30) -> List[dict]:
        """Load historical candles from MT5 gateway.
        
        Returns list of candles with OHLCV data.
        Each candle: {"time": "2026-07-01T00:00:00Z", "open": 1800.5, "high": 1805.0, "low": 1798.0, "close": 1802.5, "volume": 100}
        """
        # Stub - requires actual MT5 connection
        # In production, this would call MT5 gateway API
        logger.warning("HistoricalDataLoader.load_candles() is a stub. Needs MT5 gateway connection.")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Replay Runner
# ─────────────────────────────────────────────────────────────────────────────

def run_replay(
    symbols: List[str] = ["XAUUSD", "BTCUSD", "GBPJPY"],
    days: int = 30,
    timeframes: List[str] = ["M1", "M5"],
    output_path: Optional[str] = None
) -> dict:
    """Run Monte Carlo replay simulation.
    
    Args:
        symbols: List of symbols to replay
        days: Number of historical days
        timeframes: Timeframes to simulate
        output_path: Path to save report JSON
    
    Returns:
        Summary statistics dict
    """
    replay = MonteCarloReplay()
    loader = HistoricalDataLoader()
    
    logger.info(f"Starting Monte Carlo replay: {symbols} over {days} days")
    
    # Stub simulation - in production, load real candles and run through TIE pipeline
    # This is a placeholder showing the structure
    
    total_candles = days * 24 * 60  # Assuming M1 candles
    scans_per_symbol = total_candles // 10  # Scan every 10 candles
    
    for symbol in symbols:
        for i in range(scans_per_symbol):
            scan_id = str(uuid.uuid4())[:8]
            
            # Simulate gate results based on known patterns
            # In production, these would come from actual TIE pipeline execution
            
            # Market state gate
            market_state_pass = symbol == "BTCUSD" or (i % 3 == 0)  # BTCUSD 24/7
            replay.record_gate("MarketState", "PASS" if market_state_pass else "FAIL")
            
            # Opportunity gate
            opportunity_pass = i % 5 == 0
            replay.record_gate("Opportunity", "PASS" if opportunity_pass else "FAIL")
            
            # Detector gate
            detector_pass = opportunity_pass and (i % 4 == 0)
            replay.record_gate("Detector", "PASS" if detector_pass else "FAIL" if opportunity_pass else "SKIPPED")
            
            # Risk gate
            risk_pass = detector_pass and (i % 3 == 0)
            replay.record_gate("RiskGate", "PASS" if risk_pass else "FAIL" if detector_pass else "SKIPPED")
            
            result = ReplayResult(
                scan_id=scan_id,
                symbol=symbol,
                timestamp=datetime.now(timezone.utc).isoformat(),
                strategy="MonteCarlo",
                signal_generated=detector_pass,
                trade_executed=risk_pass,
                rejection_reason="" if risk_pass else "RiskGate:RR" if detector_pass else "Detector:confidence"
            )
            
            replay.record_scan(result)
    
    # Generate report
    report = replay.get_summary()
    report_text = replay.generate_report()
    
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        logger.info(f"Report saved to {output_path}")
    
    print(report_text)
    return report


# ─────────────────────────────────────────────────────────────────────────────
# CLI Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Monte Carlo Replay Engine")
    parser.add_argument("--symbols", nargs="+", default=["XAUUSD", "BTCUSD", "GBPJPY"], help="Symbols to replay")
    parser.add_argument("--days", type=int, default=30, help="Number of days to replay")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(message)s')
    
    run_replay(
        symbols=args.symbols,
        days=args.days,
        output_path=args.output
    )
