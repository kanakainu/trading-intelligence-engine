"""Modular risk policies for the Risk Engine. Each policy is independent."""
from typing import Any, Dict
from core.execution.execution_contract import ExecutionContract
from risk.registry import RiskPolicyBase

# Mocked external dependencies (replace with actual adapters in runtime)
class MockBrokerAdapter:
    def __init__(self, positions=None, account_info=None):
        self._positions = positions if positions is not None else []
        self._account_info = account_info if account_info is not None else {"balance": 10000.0, "equity": 9500.0, "free_margin": 8000.0}
    def get_account_info(self): return self._account_info
    def get_positions(self): return self._positions

class MockMarketAdapter:
    def __init__(self, snapshot=None):
        self._snapshot = snapshot if snapshot is not None else {"last_price": 1.0, "spread": 0.0001}
    def get_market_snapshot(self, symbol): return self._snapshot

# ── Individual Risk Policies ───────────────────────────────────────────────

class MaxPositionSizePolicy(RiskPolicyBase):
    name: str = "max_position_size"

    def evaluate(self, contract: ExecutionContract, config: Dict[str, Any]) -> (bool, str):
        max_volume = config.get("max_volume", 1.0)
        volume = contract.metadata.get("volume", 0.0)
        if volume > max_volume:
            return False, f"Volume {volume} exceeds max {max_volume}"
        return True, ""


class MaxOpenPositionsPolicy(RiskPolicyBase):
    name: str = "max_open_positions"

    def __init__(self, broker_adapter=None):
        self.broker_adapter = broker_adapter or MockBrokerAdapter()

    def evaluate(self, contract: ExecutionContract, config: Dict[str, Any]) -> (bool, str):
        max_count = config.get("max_count", 5)
        open_positions = self.broker_adapter.get_positions()
        if len(open_positions) >= max_count:
            return False, f"Open positions {len(open_positions)} exceeds max {max_count}"
        return True, ""


class DailyLossLimitPolicy(RiskPolicyBase):
    name: str = "daily_loss_limit"

    def evaluate(self, contract: ExecutionContract, config: Dict[str, Any]) -> (bool, str):
        max_loss = config.get("max_loss_usd", 100.0)
        return True, ""


class MaximumDrawdownPolicy(RiskPolicyBase):
    name: str = "maximum_drawdown"

    def evaluate(self, contract: ExecutionContract, config: Dict[str, Any]) -> (bool, str):
        max_dd_percent = config.get("max_drawdown_percent", 0.05)
        return True, ""


class MarginAvailabilityPolicy(RiskPolicyBase):
    name: str = "margin_availability"

    def __init__(self, broker_adapter=None):
        self.broker_adapter = broker_adapter or MockBrokerAdapter()

    def evaluate(self, contract: ExecutionContract, config: Dict[str, Any]) -> (bool, str):
        min_free_margin_percent = config.get("min_free_margin_percent", 0.1)
        account_info = self.broker_adapter.get_account_info()
        balance = account_info.get("balance", 0.0)
        free_margin = account_info.get("free_margin", 0.0)

        if balance <= 0: return False, "Account balance non-positive"

        if free_margin / balance < min_free_margin_percent:
            return False, f"Free margin {free_margin} below {min_free_margin_percent * 100}% of balance"
        return True, ""


class MinimumRiskRewardPolicy(RiskPolicyBase):
    name: str = "minimum_risk_reward"

    def evaluate(self, contract: ExecutionContract, config: Dict[str, Any]) -> (bool, str):
        min_rr = config.get("min_rr", 1.5)
        if not contract.sl or not contract.tp:
            return False, "Stop loss or take profit not defined for R/R calculation"

        mock_entry_price = contract.entry if contract.entry else 0.0

        risk = abs(mock_entry_price - contract.sl)
        reward = abs(contract.tp - mock_entry_price)

        if risk == 0: return False, "Risk cannot be zero"

        current_rr = reward / risk
        if current_rr < min_rr:
            return False, f"R/R {current_rr:.2f} below min {min_rr}"
        return True, ""


class MarketAvailabilityPolicy(RiskPolicyBase):
    name: str = "market_availability"

    def __init__(self, market_adapter=None):
        self.market_adapter = market_adapter or MockMarketAdapter()

    def evaluate(self, contract: ExecutionContract, config: Dict[str, Any]) -> (bool, str):
        snapshot = self.market_adapter.get_market_snapshot(contract.symbol)
        if not snapshot:
            return False, f"Market data unavailable for {contract.symbol}"
        return True, ""


class DuplicatePositionPreventionPolicy(RiskPolicyBase):
    name: str = "duplicate_position_prevention"

    def __init__(self, broker_adapter=None):
        self.broker_adapter = broker_adapter or MockBrokerAdapter()

    def evaluate(self, contract: ExecutionContract, config: Dict[str, Any]) -> (bool, str):
        open_positions = self.broker_adapter.get_positions()
        for pos in open_positions:
            if pos.get("symbol") == contract.symbol and pos.get("side") == contract.direction:
                return False, f"Duplicate {contract.direction} position for {contract.symbol} already exists"
        return True, ""
