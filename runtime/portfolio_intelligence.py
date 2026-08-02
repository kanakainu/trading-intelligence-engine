"""Portfolio Intelligence — cross-pair exposure coordination.

Gold BUY + BTC BUY + USD strong → reduce exposure.

NO trading logic. Pure risk coordination.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
import logging

log = logging.getLogger("PortfolioIntelligence")


@dataclass
class Position:
    symbol: str
    direction: str  # BUY | SELL
    volume: float
    entry: float
    pnl: float
    strategy: str = ""


@dataclass
class ExposureCheck:
    total_long_usd: float
    total_short_usd: float
    net_exposure: float
    correlated_pairs: List[str]
    recommendation: str
    status: str  # OK | WARN | CRITICAL


class PortfolioCoordinator:
    """Coordinate exposure across pairs.

    Job:
    - Check net exposure (long vs short)
    - Detect correlated positions (same direction)
    - Recommend rebalancing if over-exposed
    """

    # Correlation groups (simplified)
    CORRELATION_GROUPS = {
        "USD_WEAK": ["XAUUSD", "BTCUSD"],  # Buy these = USD weak
        "USD_STRONG": [],  # Sell these = USD weak
    }

    MAX_EXPOSURE_USD = 500.0  # Max net exposure in USD notional

    def __init__(self, max_exposure: float = 500.0):
        self.MAX_EXPOSURE_USD = max_exposure

    def check_exposure(self, positions: List[Position]) -> ExposureCheck:
        """Check current portfolio exposure."""
        total_long = 0.0
        total_short = 0.0
        correlated_pairs = []

        for pos in positions:
            notional = pos.volume * pos.entry * 100  # Approximate
            if pos.direction == "BUY":
                total_long += notional
            else:
                total_short += notional

        net_exposure = total_long - total_short

        # Check correlation (same direction on correlated pairs)
        long_symbols = [p.symbol for p in positions if p.direction == "BUY"]
        for group_name, symbols in self.CORRELATION_GROUPS.items():
            matches = [s for s in long_symbols if s in symbols]
            if len(matches) >= 2:
                correlated_pairs.extend(matches)

        # Determine status
        status = "OK"
        recommendation = ""
        if abs(net_exposure) > self.MAX_EXPOSURE_USD:
            status = "WARN"
            recommendation = f"Net exposure ${abs(net_exposure):.0f} > ${self.MAX_EXPOSURE_USD} limit. Consider reducing positions."
        if abs(net_exposure) > self.MAX_EXPOSURE_USD * 2:
            status = "CRITICAL"
            recommendation = f"EXPOSURE CRITICAL: ${abs(net_exposure):.0f}. Immediate action required."

        if correlated_pairs and status != "CRITICAL":
            status = "WARN"
            recommendation = f"Correlated positions: {correlated_pairs}. Risk of simultaneous loss."

        return ExposureCheck(
            total_long_usd=total_long,
            total_short_usd=total_short,
            net_exposure=net_exposure,
            correlated_pairs=list(set(correlated_pairs)),
            recommendation=recommendation,
            status=status,
        )

    def can_open_position(self, positions: List[Position], new_symbol: str, new_direction: str, new_volume: float, new_entry: float) -> tuple[bool, str]:
        """Check if opening new position is safe."""
        check = self.check_exposure(positions)

        # Simulate new position
        new_notional = new_volume * new_entry * 100
        if new_direction == "BUY":
            test_net = check.net_exposure + new_notional
        else:
            test_net = check.net_exposure - new_notional

        if abs(test_net) > self.MAX_EXPOSURE_USD * 1.5:
            return False, f"Exposure limit exceeded: ${abs(test_net):.0f} > ${self.MAX_EXPOSURE_USD * 1.5}"

        # Check correlation
        if new_direction == "BUY" and new_symbol in self.CORRELATION_GROUPS.get("USD_WEAK", []):
            existing = [p.symbol for p in positions if p.direction == "BUY" and p.symbol in self.CORRELATION_GROUPS.get("USD_WEAK", [])]
            if len(existing) >= 2:
                return False, f"Too many correlated long positions: {existing}"

        return True, ""
