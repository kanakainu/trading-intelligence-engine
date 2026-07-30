"""Test Phase 4.6 — Risk Layer."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from decimal import Decimal
from typing import Any, Dict

from core.execution.execution_contract import ExecutionContract
from risk.engine import RiskEngine
from risk.config import RiskConfig, PolicyConfig
from risk.models import RiskDecision, RiskAuditRecord, RiskHealthReport
from risk.registry import PolicyRegistry, RiskPolicyBase
from risk.audit import RiskAuditTrail
from risk.health import RiskHealthMonitor
from risk.exceptions import RiskEvaluationError, PolicyExecutionError, ConfigurationError
from risk.policies import (
    MaxPositionSizePolicy, MaxOpenPositionsPolicy,
    DailyLossLimitPolicy, MaximumDrawdownPolicy,
    MarginAvailabilityPolicy, MinimumRiskRewardPolicy,
    MarketAvailabilityPolicy, DuplicatePositionPreventionPolicy,
    MockBrokerAdapter, MockMarketAdapter,
)


def make_contract(**kwargs):
    defaults = dict(
        contract_id="t01", action="ENTRY", symbol="XAUUSD",
        methodology="test", setup="test", entry_pattern="test",
        confidence=0.8, direction="BUY",
        entry=1.08, sl=1.079, tp=1.082,
        reason="test", metadata={},
    )
    defaults.update(kwargs)
    return ExecutionContract(**defaults)


@pytest.fixture
def default_contract():
    return make_contract()


@pytest.fixture
def default_config():
    cfg = RiskConfig.default()
    cfg.policies["max_position_size"].params["max_volume"] = 0.5
    cfg.policies["max_open_positions"].params["max_count"] = 2
    cfg.policies["minimum_risk_reward"].params["min_rr"] = 1.5
    cfg.policies["margin_availability"].params["min_free_margin_percent"] = 0.1
    return cfg


@pytest.fixture
def policy_registry():
    reg = PolicyRegistry()
    reg.register("max_position_size", MaxPositionSizePolicy)
    reg.register("max_open_positions", MaxOpenPositionsPolicy)
    reg.register("daily_loss_limit", DailyLossLimitPolicy)
    reg.register("maximum_drawdown", MaximumDrawdownPolicy)
    reg.register("margin_availability", MarginAvailabilityPolicy)
    reg.register("minimum_risk_reward", MinimumRiskRewardPolicy)
    reg.register("market_availability", MarketAvailabilityPolicy)
    reg.register("duplicate_position_prevention", DuplicatePositionPreventionPolicy)
    return reg


@pytest.fixture
def risk_engine(default_config, policy_registry):
    return RiskEngine(default_config, policy_registry, RiskAuditTrail(), RiskHealthMonitor())


# ── max_position_size ──────────────────────────────────────────────────────
def test_max_pos_size_approve(risk_engine, default_contract):
    default_contract.metadata["volume"] = 0.3
    d = risk_engine.evaluate(default_contract)
    assert d.approved

def test_max_pos_size_reject(risk_engine):
    c = make_contract(metadata={"volume": 1.0})
    d = risk_engine.evaluate(c)
    assert not d.approved
    assert d.triggered_policy == "max_position_size"


# ── max_open_positions ─────────────────────────────────────────────────────
def test_max_open_positions_approve(default_config, default_contract):
    # Fresh registry with MockBrokerAdapter(positions=[])
    class OkPolicy(MaxOpenPositionsPolicy):
        def __init__(self): super().__init__(broker_adapter=MockBrokerAdapter(positions=[]))
    reg = PolicyRegistry(); reg.register("max_open_positions", OkPolicy)
    default_config.policies = {"max_open_positions": PolicyConfig(enabled=True, params={"max_count": 2})}
    e = RiskEngine(default_config, reg, RiskAuditTrail(), RiskHealthMonitor())
    assert e.evaluate(default_contract).approved

def test_max_open_positions_reject(default_config, default_contract):
    class FullPolicy(MaxOpenPositionsPolicy):
        def __init__(self):
            super().__init__(broker_adapter=MockBrokerAdapter(positions=[{"s":1},{"s":2}]))
    reg = PolicyRegistry(); reg.register("max_open_positions", FullPolicy)
    default_config.policies = {"max_open_positions": PolicyConfig(enabled=True, params={"max_count": 2})}
    e = RiskEngine(default_config, reg, RiskAuditTrail(), RiskHealthMonitor())
    d = e.evaluate(default_contract)
    assert not d.approved
    assert d.triggered_policy == "max_open_positions"


# ── daily_loss_limit / maximum_drawdown (always approve for now) ───────────
def test_daily_loss_approves(risk_engine, default_contract):
    default_contract.metadata["volume"] = 0.1
    d = risk_engine.evaluate(default_contract)
    assert d.approved  # daily_loss always approve currently


# ── margin_availability ────────────────────────────────────────────────────
def test_margin_approve(default_config, default_contract):
    class OkMargin(MarginAvailabilityPolicy):
        def __init__(self):
            super().__init__(broker_adapter=MockBrokerAdapter(
                account_info={"balance": 10000.0, "free_margin": 5000.0}))
    reg = PolicyRegistry(); reg.register("margin_availability", OkMargin)
    default_config.policies = {"margin_availability": PolicyConfig(enabled=True,
                                params={"min_free_margin_percent": 0.1})}
    e = RiskEngine(default_config, reg, RiskAuditTrail(), RiskHealthMonitor())
    assert e.evaluate(default_contract).approved

def test_margin_reject(default_config, default_contract):
    class BadMargin(MarginAvailabilityPolicy):
        def __init__(self):
            super().__init__(broker_adapter=MockBrokerAdapter(
                account_info={"balance": 1000.0, "free_margin": 50.0}))
    reg = PolicyRegistry(); reg.register("margin_availability", BadMargin)
    default_config.policies = {"margin_availability": PolicyConfig(enabled=True,
                                params={"min_free_margin_percent": 0.1})}
    e = RiskEngine(default_config, reg, RiskAuditTrail(), RiskHealthMonitor())
    d = e.evaluate(default_contract)
    assert not d.approved
    assert d.triggered_policy == "margin_availability"


# ── minimum_risk_reward ────────────────────────────────────────────────────
def test_rr_approve(default_config, default_contract):
    # entry=1.08, sl=1.079, tp=1.082 → R/R = 0.002/0.001 = 2.0 > 1.5
    reg = PolicyRegistry(); reg.register("minimum_risk_reward", MinimumRiskRewardPolicy)
    default_config.policies = {"minimum_risk_reward": PolicyConfig(enabled=True, params={"min_rr": 1.5})}
    e = RiskEngine(default_config, reg, RiskAuditTrail(), RiskHealthMonitor())
    assert e.evaluate(default_contract).approved

def test_rr_reject(default_config):
    # entry=1.08, sl=1.07, tp=1.081 → risk=0.01, reward=0.001 → R/R=0.1 < 1.5
    c = make_contract(entry=1.08, sl=1.07, tp=1.081)
    reg = PolicyRegistry(); reg.register("minimum_risk_reward", MinimumRiskRewardPolicy)
    default_config.policies = {"minimum_risk_reward": PolicyConfig(enabled=True, params={"min_rr": 1.5})}
    e = RiskEngine(default_config, reg, RiskAuditTrail(), RiskHealthMonitor())
    d = e.evaluate(c)
    assert not d.approved
    assert d.triggered_policy == "minimum_risk_reward"


# ── market_availability ────────────────────────────────────────────────────
def test_market_approve(default_config, default_contract):
    class OkMarket(MarketAvailabilityPolicy):
        def __init__(self):
            super().__init__(market_adapter=MockMarketAdapter(snapshot={"price": 1.0}))
    reg = PolicyRegistry(); reg.register("market_availability", OkMarket)
    default_config.policies = {"market_availability": PolicyConfig(enabled=True)}
    e = RiskEngine(default_config, reg, RiskAuditTrail(), RiskHealthMonitor())
    assert e.evaluate(default_contract).approved

def test_market_reject(default_config, default_contract):
    class NoMarket(MarketAvailabilityPolicy):
        def __init__(self):
            super().__init__(market_adapter=MockMarketAdapter(snapshot={}))
    reg = PolicyRegistry(); reg.register("market_availability", NoMarket)
    default_config.policies = {"market_availability": PolicyConfig(enabled=True)}
    e = RiskEngine(default_config, reg, RiskAuditTrail(), RiskHealthMonitor())
    d = e.evaluate(default_contract)
    assert not d.approved
    assert d.triggered_policy == "market_availability"


# ── duplicate_position ─────────────────────────────────────────────────────
def test_dup_approve(default_config, default_contract):
    class NoDup(DuplicatePositionPreventionPolicy):
        def __init__(self):
            super().__init__(broker_adapter=MockBrokerAdapter(positions=[]))
    reg = PolicyRegistry(); reg.register("duplicate_position_prevention", NoDup)
    default_config.policies = {"duplicate_position_prevention": PolicyConfig(enabled=True)}
    e = RiskEngine(default_config, reg, RiskAuditTrail(), RiskHealthMonitor())
    assert e.evaluate(default_contract).approved

def test_dup_reject(default_config, default_contract):
    class HasDup(DuplicatePositionPreventionPolicy):
        def __init__(self):
            super().__init__(broker_adapter=MockBrokerAdapter(
                positions=[{"symbol": "XAUUSD", "side": "BUY"}]))
    reg = PolicyRegistry(); reg.register("duplicate_position_prevention", HasDup)
    default_config.policies = {"duplicate_position_prevention": PolicyConfig(enabled=True)}
    e = RiskEngine(default_config, reg, RiskAuditTrail(), RiskHealthMonitor())
    d = e.evaluate(default_contract)
    assert not d.approved
    assert d.triggered_policy == "duplicate_position_prevention"


# ── global disabled ────────────────────────────────────────────────────────
def test_global_disabled(default_config, policy_registry, default_contract):
    default_config.global_enabled = False
    e = RiskEngine(default_config, policy_registry, RiskAuditTrail(), RiskHealthMonitor())
    assert e.evaluate(default_contract).approved


# ── single policy disabled ─────────────────────────────────────────────────
def test_single_policy_disabled(default_contract):
    cfg = RiskConfig.default()
    cfg.policies["max_position_size"].enabled = False
    cfg.policies["max_position_size"].params["max_volume"] = 0.5
    reg = PolicyRegistry()
    reg.register("max_position_size", MaxPositionSizePolicy)
    e = RiskEngine(cfg, reg, RiskAuditTrail(), RiskHealthMonitor())
    c = make_contract(metadata={"volume": 1.0})  # would fail if enabled
    assert e.evaluate(c).approved  # disabled → no check → approve


# ── audit ──────────────────────────────────────────────────────────────────
def test_audit_on_evaluate(risk_engine, default_contract):
    default_contract.metadata["volume"] = 0.1
    before = len(risk_engine._audit_trail.get_records())
    risk_engine.evaluate(default_contract)
    assert len(risk_engine._audit_trail.get_records()) == before + 1

def test_audit_content(risk_engine, default_contract):
    default_contract.metadata["volume"] = 0.1
    d = risk_engine.evaluate(default_contract)
    rec = risk_engine._audit_trail.get_records()[-1]
    assert rec.execution_id == d.execution_id
    assert rec.approved == d.approved


# ── health ─────────────────────────────────────────────────────────────────
def test_health_updates(risk_engine, default_contract):
    default_contract.metadata["volume"] = 0.1
    before = risk_engine._health_monitor.get_report().evaluations
    risk_engine.evaluate(default_contract)
    assert risk_engine._health_monitor.get_report().evaluations == before + 1

def test_health_rejection_rate(risk_engine):
    c = make_contract(metadata={"volume": 1.0})  # will be rejected
    risk_engine.evaluate(c)
    assert risk_engine._health_monitor.get_report().rejection_rate > 0


# ── policy error propagates ────────────────────────────────────────────────
def test_policy_error_propagates(default_config, default_contract):
    class Buggy(RiskPolicyBase):
        name = "buggy"
        def evaluate(self, contract, config): raise ValueError("bug!")
    reg = PolicyRegistry(); reg.register("buggy", Buggy)
    default_config.policies = {"buggy": PolicyConfig(enabled=True)}
    e = RiskEngine(default_config, reg, RiskAuditTrail(), RiskHealthMonitor())
    with pytest.raises(PolicyExecutionError):
        e.evaluate(default_contract)


# ── exceptions ─────────────────────────────────────────────────────────────
def test_exceptions():
    from risk.exceptions import RiskEvaluationError, PolicyExecutionError, RiskEngineUnavailableError
    with pytest.raises(RiskEvaluationError): raise RiskEvaluationError("x")
    with pytest.raises(PolicyExecutionError): raise PolicyExecutionError("x")
    with pytest.raises(RiskEngineUnavailableError): raise RiskEngineUnavailableError("x")


# ── phase 3 frozen ─────────────────────────────────────────────────────────
def test_phase3_frozen():
    from core.decision.decision_pipeline import DecisionPipeline
    assert DecisionPipeline
