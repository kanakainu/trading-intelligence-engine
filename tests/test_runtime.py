"""Test Phase 4.5 — Intelligence Runtime."""
import pytest, sys, os, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from runtime import (
    IntelligenceRuntime, RuntimeState, RuntimeEvent, EventType,
    ExecutionContext, Dispatcher, PipelineOrchestrator, ComponentRegistry, RuntimeHealth,
)
from runtime.exceptions import (
    RuntimeInitializationError, PipelineExecutionError, ContextBuildError,
    DispatcherError, RuntimeStateError
)

# ── Fixture ────────────────────────────────────────────────────────────────
@pytest.fixture
def rt():
    return IntelligenceRuntime()

# ── Lifecycle ──────────────────────────────────────────────────────────────
def test_initial_state(rt):   assert rt.get_state() == RuntimeState.CREATED
def test_initialize(rt):
    rt.initialize()
    assert rt.get_state() == RuntimeState.INITIALIZED
def test_start(rt):
    rt.initialize(); rt.start()
    assert rt.get_state() == RuntimeState.RUNNING
def test_pause(rt):
    rt.initialize(); rt.start(); rt.pause()
    assert rt.get_state() == RuntimeState.PAUSED
def test_resume(rt):
    rt.initialize(); rt.start(); rt.pause(); rt.resume()
    assert rt.get_state() == RuntimeState.RUNNING
def test_stop(rt):
    rt.initialize(); rt.start(); rt.stop()
    assert rt.get_state() == RuntimeState.STOPPED
def test_shutdown(rt):
    rt.initialize(); rt.start(); rt.shutdown()
    assert rt.get_state() == RuntimeState.SHUTDOWN
def test_double_initialize_fails(rt):
    rt.initialize()
    with pytest.raises(RuntimeStateError): rt.initialize()
def test_start_before_initialize_fails(rt):
    with pytest.raises(RuntimeStateError): rt.start()

# ── Context Builder ───────────────────────────────────────────────────────
def test_build_context(rt):
    ctx = rt.build_context({"price":2000}, {"memory":"ok"}, {"version":"1.0"})
    assert isinstance(ctx, ExecutionContext)
    assert ctx.market.get("price") == 2000
    assert ctx.memory.get("memory") == "ok"

# ── Pipeline orchestration ────────────────────────────────────────────────
def test_pipeline_execution(rt):
    calls = []
    def step1(ctx):
        calls.append("step1")
        ctx.metadata["step1"] = "done"
        return ctx
    rt.register_pipeline_step(step1)
    rt.initialize()
    rt.start()
    ctx = rt.execute(ExecutionContext(execution_id="e01"))
    assert ctx.metadata.get("step1") == "done"
    assert "e01" in ctx.execution_id

def test_pipeline_multi_step(rt):
    steps = []
    def s1(ctx): steps.append("s1"); ctx.metadata["s1"]=True; return ctx
    def s2(ctx): steps.append("s2"); ctx.metadata["s2"]=True; return ctx
    rt.register_pipeline_step(s1)
    rt.register_pipeline_step(s2)
    rt.initialize(); rt.start()
    ctx = rt.execute(ExecutionContext())
    assert steps == ["s1", "s2"]

def test_pipeline_exception(rt):
    def bad(ctx): raise ValueError("oops")
    rt.register_pipeline_step(bad)
    rt.initialize(); rt.start()
    with pytest.raises(PipelineExecutionError):
        rt.execute(ExecutionContext())

def test_execute_not_running_fails(rt):
    rt.initialize()
    with pytest.raises(RuntimeStateError):
        rt.execute(ExecutionContext())

# ── Event System ───────────────────────────────────────────────────────────
def test_subscribe_publish(rt):
    received = []
    def handler(e): received.append(e.event_type)
    rt.subscribe(EventType.RUNTIME_WARNING, handler)
    rt.publish(RuntimeEvent(event_type=EventType.RUNTIME_WARNING))
    assert received[0] == EventType.RUNTIME_WARNING

def test_dispatcher_publish():
    d = Dispatcher()
    evts = []
    d.subscribe(EventType.CONTEXT_READY, lambda e: evts.append(e.event_type))
    d.publish(RuntimeEvent(event_type=EventType.CONTEXT_READY))
    assert len(evts) == 1

def test_dispatcher_unsubscribe():
    d = Dispatcher()
    def h(e): pass
    d.subscribe(EventType.CONTEXT_READY, h)
    d.unsubscribe(EventType.CONTEXT_READY, h)
    # no error

# ── Registry ───────────────────────────────────────────────────────────────
def test_component_registry():
    r = ComponentRegistry()
    r.register("pipeline", object())
    assert r.exists("pipeline")
    assert r.get("pipeline") is not None

# ── Health ─────────────────────────────────────────────────────────────────
def test_health_after_start(rt):
    rt.initialize(); rt.start()
    time.sleep(0.01)
    h = rt.health()
    assert h.runtime_status == RuntimeState.RUNNING.value
    assert h.uptime_seconds > 0.0

# ── Phase 3 frozen ─────────────────────────────────────────────────────────
def test_phase3_frozen():
    from core.execution.execution_contract import ExecutionContract
    from core.decision.decision_pipeline import DecisionPipeline
    assert DecisionPipeline
