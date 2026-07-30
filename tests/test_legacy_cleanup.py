"""Test Sprint 5.8 — Legacy Cleanup & Cutover Validation."""
import pytest, sys, os, ast, pathlib
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

BANNED_IMPORTS = {
    "riri_sdk", "MarketBrain", "DecisionBrain", "RiskBrain",
    "BystraDetector", "trading_runtime_v2", "setup_builder",
    "knowledge_loader", "pack_loader",
}

BANNED_MODULES = {
    "decision_engine", "setup_resolver", "reasoning_engine",
    "detector_engine",
}

RUNTIME_FILES = list(pathlib.Path("runtime").glob("*.py"))
DETECTOR_FILES = list(pathlib.Path("detectors").glob("*.py"))
RULE_FILES = (
    list(pathlib.Path("core/rules/risk").glob("*.py")) +
    list(pathlib.Path("core/rules/plugins").glob("*.py"))
)


def check_no_banned_imports(filepath):
    """Verify a Python file has no legacy brain/sdk imports."""
    src = pathlib.Path(filepath).read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = getattr(node, "module", "") or ""
            for b in BANNED_IMPORTS:
                assert b not in mod, f"{filepath}: banned import '{b}'"


# ── No legacy imports in Runtime ───────────────────────────────────────────────
@pytest.mark.parametrize("filepath", RUNTIME_FILES)
def test_runtime_no_legacy_import(filepath):
    check_no_banned_imports(filepath)


# ── No banned modules in Detector ──────────────────────────────────────────────
@pytest.mark.parametrize("filepath", DETECTOR_FILES)
def test_detector_no_legacy_import(filepath):
    src = pathlib.Path(filepath).read_text()
    for b in ("riri_sdk", "decision_brain", "market_brain"):
        assert b not in src, f"{filepath}: banned ref '{b}'"


# ── Rule plugins clean ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("filepath", RULE_FILES)
def test_rule_no_broker_import(filepath):
    src = pathlib.Path(filepath).read_text()
    banned = ["submit_order", "mt5", "broker_adapter"]
    for b in banned:
        assert b not in src.lower(), f"{filepath}: banned ref '{b}'"


# ── ExecutionRuntime no decision logic ────────────────────────────────────────
def test_execution_runtime_no_decision_logic():
    src = pathlib.Path("runtime/execution_runtime.py").read_text()
    assert "decision_pipeline" not in src
    assert "setup_resolver" not in src
    assert "reasoning_engine" not in src
    assert "BUY" not in src or "contract.direction" in src  # BUY only from contract


# ── Full import graph: TIE core not importing riri_sdk ────────────────────────
def test_tie_core_no_riri_sdk_import():
    import subprocess
    result = subprocess.run(
        ["grep", "-rn", "-E", "--include=*.py",
         "^(import|from) riri_sdk",
         "/home/ubuntu/trading-intelligence-engine"],
        capture_output=True, text=True
    )
    lines = [l for l in result.stdout.splitlines() if "__pycache__" not in l]
    assert len(lines) == 0, "Found riri_sdk imports:\n" + "\n".join(lines)


# ── Archived legacy manifest exists ───────────────────────────────────────────
def test_archive_manifest_exists():
    assert os.path.exists("archived_legacy/dependency_audit.md")
    assert os.path.exists("archived_legacy/legacy_cleanup_report.md")


# ── Cutover integrity: key TIE modules importable ─────────────────────────────
def test_tie_modules_importable():
    from core.decision.decision_pipeline import DecisionPipeline
    from core.facts.fact_compiler import FactCompiler
    from core.setup.setup_resolver import SetupResolver
    from runtime.execution_runtime import ExecutionRuntime
    from runtime.compiler_bridge import CompilerBridge
    from core.rules.risk.risk_registry import build_risk_registry
    assert all([DecisionPipeline, FactCompiler, SetupResolver,
                ExecutionRuntime, CompilerBridge, build_risk_registry])
