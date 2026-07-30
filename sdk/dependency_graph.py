from dataclasses import dataclass, field
from typing import Set, Dict, List, Tuple


@dataclass
class DependencyEdge:
    source: str
    target: str
    allowed: bool = True


class DependencyGraph:
    def __init__(self):
        self._nodes: Set[str] = set()
        self._edges: List[DependencyEdge] = []

    def add_node(self, name: str) -> None:
        self._nodes.add(name)

    def add_edge(self, source: str, target: str) -> None:
        self._edges.append(DependencyEdge(source=source, target=target))

    def validate_layer_boundaries(self) -> List[str]:
        violations = []
        # Define architectural boundaries
        blocked = {
            "skills": {"broker", "database", "position", "strategy"},
            "strategy": {"broker"},
            "position": {"strategy", "skills"},
            "risk": {"strategy", "position"},
        }

        for src in self._nodes:
            for edge in self._edges:
                if edge.source.startswith(src) or edge.source == src:
                    for layer, banned in blocked.items():
                        if edge.source.startswith(layer) and edge.target in banned:
                            violations.append(
                                f"VIOLATION: {edge.source} depends on {edge.target} (not allowed)"
                            )
        return violations

    def detect_cycles(self) -> List[List[str]]:
        # DFS cycle detection
        visited = set()
        path = []
        cycles = []

        def dfs(node):
            if node in path:
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return
            if node in visited:
                return
            visited.add(node)
            path.append(node)
            targets = [e.target for e in self._edges if e.source == node]
            for t in targets:
                dfs(t)
            path.pop()

        for n in sorted(self._nodes):
            dfs(n)
        return cycles
