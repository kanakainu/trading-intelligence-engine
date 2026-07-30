"""Explanation — human-readable trace builder."""
from typing import Any, List


class Explanation:
    def __init__(self):
        self._lines: List[str] = []

    def add(self, label: str, passed: bool, detail: str = ""):
        mark = "✓" if passed else "✗"
        self._lines.append(f"{mark} {label}" + (f" ({detail})" if detail else ""))

    def build(self) -> str:
        return "\n".join(self._lines)
