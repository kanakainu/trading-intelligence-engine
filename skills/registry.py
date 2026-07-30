from typing import Dict, Type, List
from skills.base import BaseSkill
from skills.exceptions import SkillRegistrationError


class SkillRegistry:
    def __init__(self):
        self._skills: Dict[str, Type[BaseSkill]] = {}

    def register(self, name: str, skill_cls: Type[BaseSkill]) -> None:
        if name in self._skills:
            raise SkillRegistrationError(f"Skill '{name}' already registered")
        self._skills[name] = skill_cls

    def unregister(self, name: str) -> None:
        self._skills.pop(name, None)

    def get(self, name: str) -> Type[BaseSkill]:
        return self._skills.get(name)

    def list_available(self) -> List[str]:
        return list(self._skills.keys())
