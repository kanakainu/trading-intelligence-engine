from typing import Any, Dict, List, Optional, Type
from core.execution.execution_contract import ExecutionContract


class RiskPolicyBase:
    """Base class for all risk policies."""
    name: str = "abstract_policy"

    def __init__(self, **kwargs):
        pass

    def evaluate(self, contract: ExecutionContract, config: Dict[str, Any]) -> (bool, str):
        """Returns (approved: bool, reason: str)."""
        raise NotImplementedError


class PolicyRegistry:
    def __init__(self):
        self._policies: Dict[str, Type[RiskPolicyBase]] = {}


    def register(self, policy_name: str, policy_cls: Type[RiskPolicyBase]) -> None:
        self._policies[policy_name] = policy_cls

    def get(self, policy_name: str) -> Optional[Type[RiskPolicyBase]]:
        return self._policies.get(policy_name)

    def list_policies(self) -> List[str]:
        return list(self._policies.keys())

    def unregister(self, policy_name: str) -> None:
        self._policies.pop(policy_name, None)
