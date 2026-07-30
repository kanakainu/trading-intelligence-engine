"""Reasoning Registry — store/recall ReasoningResults."""
from typing import Dict, List, Optional
from core.reasoning.reasoning_result import ReasoningResult


class ReasoningRegistry:
    def __init__(self):
        self._store: Dict[str, ReasoningResult] = {}

    def register(self, key: str, result: ReasoningResult) -> None:
        self._store[key] = result

    def get(self, key: str) -> Optional[ReasoningResult]:
        return self._store.get(key)

    def list(self) -> List[str]:
        return list(self._store.keys())
