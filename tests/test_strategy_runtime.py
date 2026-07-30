"""Test Phase 4.9 — Strategy Runtime."""
import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import MagicMock
from strategy.runtime import StrategyRuntime
from strategy.registry import StrategyRegistry
from strategy.models import StrategyDefinition, StrategyStatus
from strategy.exceptions import StrategyLoadError, StrategyExecutionError
from skills.manager import SkillManager
from skills.registry import SkillRegistry
from skills.builtins.session_skill import SessionSkill, TrendSkill


@pytest.fixture
def skill_manager():
    reg = SkillRegistry()
    reg.register("session", SessionSkill)
    reg.register("trend", TrendSkill)
    mgr = SkillManager(reg)
    mgr.load_skill("session")
    mgr.load_skill("trend")
    return mgr


@pytest.fixture
def mock_compiler():
    m = MagicMock()
    # Mock Decision Contract
    m.compile.return_value = {"approved": True, "action": "BUY", "confidence": 0.8}
    return m


@pytest.fixture
def runtime(skill_manager, mock_compiler):
    r = StrategyRuntime(skill_manager, mock_compiler)
    r.initialize()
    return r


def test_strategy_registration(runtime):
    defn = StrategyDefinition(
        strategy_id="scalp_v1",
        strategy_name="Scalper",
        version="1.0.0",
        required_skills=["session", "trend"]
    )
    runtime._registry.register(defn)
    assert "scalp_v1" in runtime._registry.list_strategies()


def test_strategy_lifecycle(runtime):
    defn = StrategyDefinition(strategy_id="s1", strategy_name="S1", version="1")
    runtime._registry.register(defn)
    
    runtime.load_strategy("s1")
    assert runtime._registry.get_status("s1") == StrategyStatus.LOADED
    
    runtime.activate_strategy("s1")
    assert runtime._registry.get_status("s1") == StrategyStatus.READY
    assert runtime._active_strategy_id == "s1"
    
    runtime.deactivate_strategy("s1")
    assert runtime._active_strategy_id is None
    assert runtime._registry.get_status("s1") == StrategyStatus.STOPPED


def test_strategy_execution(runtime, mock_compiler):
    defn = StrategyDefinition(
        strategy_id="scalp",
        strategy_name="Scalper",
        version="1.0.0",
        required_skills=["session", "trend"]
    )
    runtime._registry.register(defn)
    runtime.activate_strategy("scalp")
    
    market = {"price": 2000.0}
    memory = {"last_trade": "none"}
    
    decision = runtime.execute(market, memory)
    
    assert decision["approved"] is True
    assert mock_compiler.compile.called
    assert runtime.health_check().execution_count == 1


def test_health_report(runtime):
    report = runtime.health_check()
    assert report.status == "INITIALIZED"
    assert report.execution_count == 0


def test_event_dispatching(runtime):
    events = []
    def publish(ev, payload): events.append(ev)
    runtime.set_publish_fn(publish)
    
    defn = StrategyDefinition(strategy_id="s1", strategy_name="S1", version="1")
    runtime._registry.register(defn)
    runtime.activate_strategy("s1")
    
    runtime.execute({"p": 1}, {})
    assert "DECISION_RECEIVED" in events


def test_execution_failure(runtime, mock_compiler):
    mock_compiler.compile.side_effect = Exception("Compiler error")
    defn = StrategyDefinition(strategy_id="s1", strategy_name="S1", version="1")
    runtime._registry.register(defn)
    runtime.activate_strategy("s1")
    
    with pytest.raises(StrategyExecutionError):
        runtime.execute({}, {})
    
    assert runtime._registry.get_status("s1") == StrategyStatus.FAILED


def test_load_nonexistent(runtime):
    with pytest.raises(StrategyLoadError):
        runtime.load_strategy("none")
