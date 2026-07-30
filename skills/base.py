from abc import ABC, abstractmethod
from typing import Any, Dict
from skills.context import SkillContext, SkillResult, SkillStatus


class BaseSkill(ABC):
    name: str = "abstract_skill"

    def __init__(self):
        self.status = SkillStatus.REGISTERED

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def execute(self, context: SkillContext) -> SkillResult:
        pass

    @abstractmethod
    def validate(self) -> bool:
        pass

    @abstractmethod
    def shutdown(self) -> None:
        pass

    def health_check(self) -> Dict[str, Any]:
        return {"name": self.name, "status": self.status.value}
