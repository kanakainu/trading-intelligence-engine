from typing import List, Dict
from skills.manager import SkillManager
from skills.context import SkillContext, SkillResult


class SkillPipeline:
    def __init__(self, manager: SkillManager):
        self._manager = manager
        self._sequence: List[str] = []

    def add_step(self, skill_name: str) -> None:
        self._sequence.append(skill_name)

    def execute(self, context: SkillContext) -> List[SkillResult]:
        results = []
        for skill_name in self._sequence:
            res = self._manager.execute_skill(skill_name, context)
            results.append(res)
            # Update context for next skill if needed (optional coupling)
            context.runtime_context[f"last_skill_{skill_name}"] = res.findings
        return results
