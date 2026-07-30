"""Rule Plugin Interface — base contract for all Rule Plugins."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RuleResult:
    status: str  # APPROVE | REJECT | MODIFIED
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0


class RulePluginInterface(ABC):
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None: pass

    @abstractmethod
    def evaluate(self, context: Dict[str, Any], facts: Dict[str, Any],
                 setup_result: Any = None, decision: Any = None) -> RuleResult: pass

    @abstractmethod
    def metadata(self) -> Dict[str, Any]: pass

    @abstractmethod
    def priority(self) -> int: pass

    @abstractmethod
    def enabled(self) -> bool: pass
