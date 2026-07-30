"""Risk Engine — centralized layer to evaluate Execution Contracts.
Final authority for approving/rejecting trade execution. No order bypasses this.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from core.execution.execution_contract import ExecutionContract
from risk.config import RiskConfig, PolicyConfig
from risk.models import RiskDecision, RiskAuditRecord
from risk.registry import PolicyRegistry, RiskPolicyBase
from risk.audit import RiskAuditTrail
from risk.health import RiskHealthMonitor
from risk.exceptions import RiskEvaluationError, PolicyExecutionError, ConfigurationError


class RiskEngine:
    def __init__(self, config: RiskConfig, registry: PolicyRegistry,
                 audit_trail: RiskAuditTrail, health_monitor: RiskHealthMonitor):
        self._config = config
        self._registry = registry
        self._audit_trail = audit_trail
        self._health_monitor = health_monitor

    def evaluate(self, contract: ExecutionContract) -> RiskDecision:
        if not self._config.global_enabled:
            return self._approve_decision(contract.contract_id, "Risk engine globally disabled")

        decision = RiskDecision(approved=True, execution_id=contract.contract_id)
        active_policies: List[str] = []
        reasons: List[str] = []

        for policy_name, policy_cls in self._registry._policies.items():
            policy_cfg = self._config.get_policy_config(policy_name)
            if not policy_cfg.enabled: continue

            active_policies.append(policy_name)

            try:
                policy_instance = policy_cls()
                approved, reason = policy_instance.evaluate(contract, policy_cfg.params)
                decision.policy_results[policy_name] = {"approved": approved, "reason": reason}

                if not approved:
                    decision.approved = False
                    decision.score -= 10 # Penalize for each rejected policy
                    reasons.append(f"Policy '{policy_name}' rejected: {reason}")
                    decision.triggered_policy = policy_name # First blocking policy
                    break # Stop pipeline on first rejection
            except Exception as e:
                raise PolicyExecutionError(f"Policy '{policy_name}' failed: {e}") from e

        decision.reasons = reasons
        self._audit_trail.record(RiskAuditRecord(
            execution_id=decision.execution_id, approved=decision.approved,
            score=decision.score, triggered_policy=decision.triggered_policy,
            reasons=decision.reasons
        ))
        self._health_monitor.update_evaluation(decision.approved, active_policies)

        return decision

    def _approve_decision(self, execution_id: str, reason: str) -> RiskDecision:
        decision = RiskDecision(approved=True, execution_id=execution_id, reasons=[reason])
        self._audit_trail.record(RiskAuditRecord(
            execution_id=execution_id, approved=True, score=100.0, reasons=[reason]
        ))
        self._health_monitor.update_evaluation(True, self._config.list_enabled_policies())
        return decision

    def approve(self, contract: ExecutionContract) -> RiskDecision:
        return self._approve_decision(contract.contract_id, "Manually approved")

    def reject(self, contract: ExecutionContract, reason: str = "Manually rejected") -> RiskDecision:
        decision = RiskDecision(approved=False, execution_id=contract.contract_id, reasons=[reason])
        self._audit_trail.record(RiskAuditRecord(
            execution_id=contract.contract_id, approved=False, score=0.0, reasons=[reason]
        ))
        self._health_monitor.update_evaluation(False, self._config.list_enabled_policies())
        return decision

    def explain(self, decision: RiskDecision) -> str:
        if decision.approved:
            return f"Approved (Score: {decision.score}). Reasons: {', '.join(decision.reasons)}"
        else:
            return f"Rejected (Score: {decision.score}). Triggered policy: {decision.triggered_policy}. Reasons: {', '.join(decision.reasons)}"
