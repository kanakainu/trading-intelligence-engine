import time
from typing import Dict, List, Optional, Any
from skills.base import BaseSkill
from skills.registry import SkillRegistry
from skills.context import SkillContext, SkillResult, SkillStatus, SkillHealth
from skills.exceptions import SkillUnavailableError, SkillExecutionError


class SkillManager:
    def __init__(self, registry: SkillRegistry):
        self._registry = registry
        self._instances: Dict[str, BaseSkill] = {}
        self._health: Dict[str, SkillHealth] = {}

    def load_skill(self, name: str, config: Optional[Dict[str, Any]] = None) -> None:
        skill_cls = self._registry.get(name)
        if not skill_cls:
            raise SkillUnavailableError(f"Skill '{name}' not found in registry")
        
        instance = skill_cls()
        instance.initialize(config or {})
        instance.status = SkillStatus.READY
        self._instances[name] = instance
        self._health[name] = SkillHealth(name=name, status=SkillStatus.READY)

    def execute_skill(self, name: str, context: SkillContext) -> SkillResult:
        skill = self._instances.get(name)
        if not skill or skill.status != SkillStatus.READY:
            raise SkillUnavailableError(f"Skill '{name}' is not ready")

        start_time = time.time()
        try:
            skill.status = SkillStatus.RUNNING
            result = skill.execute(context)
            skill.status = SkillStatus.READY
            
            # Update health
            h = self._health[name]
            h.evaluations += 1
            exec_time = (time.time() - start_time) * 1000
            h.avg_execution_ms = (h.avg_execution_ms * (h.evaluations - 1) + exec_time) / h.evaluations
            result.execution_time_ms = exec_time
            
            return result
        except Exception as e:
            skill.status = SkillStatus.FAILED
            self._health[name].failures += 1
            self._health[name].last_error = str(e)
            raise SkillExecutionError(f"Error executing skill '{name}': {e}") from e

    def get_health_report(self) -> Dict[str, Any]:
        return {
            "loaded_skills": list(self._instances.keys()),
            "enabled_skills": [n for n, s in self._instances.items() if s.status == SkillStatus.READY],
            "failed_skills": [n for n, h in self._health.items() if h.failures > 0],
            "average_execution_ms": sum(h.avg_execution_ms for h in self._health.values()) / max(len(self._health), 1),
            "status": "OPERATIONAL"
        }
