"""Architecture rules — enforce Blueprint v1.0 contracts."""
import ast, importlib, inspect, sys, os, pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def get_imports(module_path: str):
    with open(module_path) as f:
        tree = ast.parse(f.read())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
    return imports


def get_core_file(subpath):
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    return os.path.join(base, "core", subpath)


def test_loader_does_not_import_detector():
    imps = get_imports(get_core_file("compiler/knowledge_loader.py"))
    assert "detectors" not in imps, "KnowledgeLoader must not import detectors"

def test_detector_does_not_import_yaml():
    imps = get_imports(get_core_file("detectors/detector_engine.py"))
    assert "yaml" not in imps, "DetectorEngine must not import yaml"

def test_setup_does_not_import_yaml():
    imps = get_imports(get_core_file("setup/setup_engine.py"))
    assert "yaml" not in imps, "SetupEngine must not import yaml"

def test_decision_does_not_import_broker():
    imps = get_imports(get_core_file("decision/decision_engine.py"))
    for forbidden in ["mt5linux", "broker", "requests", "socket", "httpx"]:
        assert forbidden not in imps, f"DecisionEngine must not import {forbidden}"

def test_explanation_does_not_modify_decision():
    """ExplanationEngine must not write to Decision objects."""
    src = open(get_core_file("explanation/explanation_engine.py")).read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute):
                    if isinstance(target.value, ast.Name) and target.value.id == "decision":
                        pytest.fail(f"ExplanationEngine modifies decision.{target.attr}")

def test_no_circular_imports():
    """Core modules must not have circular cross-layer deps (spot check)."""
    layers = [
        "core.compiler.knowledge_loader",
        "core.graph.knowledge_graph",
        "core.context.context_engine",
        "core.detectors.detector_engine",
        "core.facts.facts_engine",
        "core.setup.setup_engine",
        "core.decision.decision_engine",
        "core.explanation.explanation_engine",
    ]
    for mod in layers:
        importlib.import_module(mod)  # would raise ImportError on cycle

def test_core_has_no_trading_methodology():
    """Core modules must not reference Bystra/ICT/SMC/CRT as standalone identifiers."""
    import ast, os, re
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'core'))
    # Match whole-word occurrences only (not substrings like CONFLICTS_WITH)
    pattern = re.compile(r'\b(Bystra|bystra|ICT|SMC|CRT)\b')
    for root, _, files in os.walk(base):
        for f in files:
            if not f.endswith(".py"):
                continue
            path = os.path.join(root, f)
            src = open(path).read()
            tree = ast.parse(src)
            # Only check string constants + identifiers, skip docstrings/comments
    # Only check string constants that are NOT file paths
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            val = node.value
            # Skip file paths — they reference pack locations, not methodology logic
            if "/" in val or "\\" in val:
                continue
            assert not pattern.search(val), \
                f"{path}: found trading methodology in string: {val!r}"
        elif isinstance(node, ast.Name):
            assert not pattern.fullmatch(node.id), \
                f"{path}: found trading methodology identifier: {node.id}"
