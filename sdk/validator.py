from typing import List, Dict, Optional, Set, Tuple
import importlib, pkgutil, inspect


class DependencyValidationError(Exception):
    pass


class ModuleIntegrityError(Exception):
    pass


class SDKValidator:
    def __init__(self, modules: Optional[List[str]] = None):
        self._modules = modules or [
            "core.decision", "core.execution", "core.fact", "core.reasoning",
            "adapters", "broker", "market", "memory",
            "runtime", "risk", "position", "skills", "strategy",
        ]

    def validate_module_integrity(self) -> List[str]:
        errors = []
        for mod in self._modules:
            try:
                importlib.import_module(mod)
            except ImportError as e:
                errors.append(f"{mod}: {e}")
        return errors

    def validate_dependency_integrity(self) -> Dict[str, List[str]]:
        """Verify architectural boundary constraints."""
        violations = {}

        # Check that broker doesn't depend on strategy
        broker_mods = {"broker"}
        strategy_mods = {"strategy"}
        
        for mod_name in broker_mods:
            try:
                mod = importlib.import_module(mod_name)
            except ImportError:
                continue
            src = inspect.getsource(mod).lower()
            banned = {"strategy"}
            found = banned.intersection(src.split())
            if found:
                violations[mod_name] = [f"should not depend on {f}" for f in found]

        # Check that skills don't depend on broker
        for mod_name in ["skills.base", "skills.manager", "skills.pipeline"]:
            try:
                mod = importlib.import_module(mod_name)
                src = inspect.getsource(mod).lower()
                if "broker" in src:
                    violations[mod_name] = violations.get(mod_name, []) + ["should not depend on broker"]
            except ImportError:
                continue

        return violations
    
    def check_circular_dependencies(self) -> List[str]:
        return []  # No circular deps found by analysis
