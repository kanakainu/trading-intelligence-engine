"""Relationship Validator — broken links, circular deps (DFS)."""
from typing import Any, Dict, List, Set


class RelationshipValidator:
    def __init__(self):
        self.errors: List[str] = []

    def check_circular(self, graph: Dict[str, List[str]]) -> List[str]:
        """DFS cycle detection."""
        visited: Dict[str, str] = {}
        cycles = []

        def dfs(node: str, path: List[str]):
            if visited.get(node) == "visiting":
                i = path.index(node)
                cycles.append("CIRCULAR:" + "→".join(path[i:] + [node]))
                return
            if visited.get(node) == "done":
                return
            visited[node] = "visiting"
            path.append(node)
            for dep in graph.get(node, []):
                dfs(dep, path)
            path.pop()
            visited[node] = "done"

        for node in graph:
            if node not in visited:
                dfs(node, [])
        return cycles
