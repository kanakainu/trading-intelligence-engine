"""Risk configuration — enables/disables policies, sets thresholds."""
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class PolicyConfig:
    enabled: bool = True
    threshold: float = 0.0
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskConfig:
    global_enabled: bool = True
    default_policy_threshold: float = 0.0
    policies: Dict[str, PolicyConfig] = field(default_factory=dict)

    def get_policy_config(self, policy_name: str) -> PolicyConfig:
        cfg = self.policies.get(policy_name, PolicyConfig())
        if not cfg.threshold: # fallback to global default if policy specific threshold not set
            cfg.threshold = self.default_policy_threshold
        return cfg

    def list_enabled_policies(self) -> List[str]:
        return [name for name, cfg in self.policies.items() if cfg.enabled]

    @classmethod
    def default(cls) -> 'RiskConfig':
        return cls(
            global_enabled=True,
            default_policy_threshold=0.0,
            policies={
                "max_position_size": PolicyConfig(enabled=True, params={"max_volume": 1.0}),
                "max_open_positions": PolicyConfig(enabled=True, params={"max_count": 5}),
                "daily_loss_limit": PolicyConfig(enabled=True, params={"max_loss_usd": 100.0}),
                "maximum_drawdown": PolicyConfig(enabled=True, params={"max_drawdown_percent": 0.05}),
                "margin_availability": PolicyConfig(enabled=True, params={"min_free_margin_percent": 0.1}),
                "minimum_risk_reward": PolicyConfig(enabled=True, params={"min_rr": 1.5}),
                "market_availability": PolicyConfig(enabled=True),
                "duplicate_position_prevention": PolicyConfig(enabled=True),
            }
        )
