"""Graph Validator — orphans, broken refs, cycles (DFS)."""
import logging
from typing import Dict, List, Tuple
from core.graph.knowledge_graph import KnowledgeGraph

log = logging.getLogger(__name__)


class GraphValidator:
    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph
        self.errors: List[str] = []

    def validate(self) -> Tuple[bool, List[str]]:
        self.errors = []
        self._check_orphan_nodes()
        self._check_broken_edges()
        self._check_cycles()
        ok = len(self.errors) == 0
        if ok:
            log.info("Graph validation passed.")
        else:
            for e in self.errors:
                log.warning(f"Graph validation error: {e}")
        return ok, self.errors

    def _check_orphan_nodes(self):
        for node_id in self.graph._nodes:
            has_out = bool(self.graph.outgoing(node_id))
            has_in  = bool(self.graph.incoming(node_id))
            if not has_out and not has_in:
                self.errors.append(f"Orphan node: {node_id}")

    def _check_broken_edges(self):
        for edge_list in self.graph._out.values():
            for edge in edge_list:
                if edge.source_id not in self.graph._nodes:
                    self.errors.append(f"Broken edge source: {edge.source_id}")
                if edge.target_id not in self.graph._nodes:
                    self.errors.append(f"Broken edge target: {edge.target_id}")

    def _check_cycles(self):
        """DFS cycle detection across all nodes."""
        visited: Dict[str, str] = {}  # node_id → 'visiting' | 'done'

        def dfs(node_id: str, path: List[str]):
            if visited.get(node_id) == 'visiting':
                cycle_start = path.index(node_id)
                self.errors.append(f"Cycle: {' → '.join(path[cycle_start:])} → {node_id}")
                return
            if visited.get(node_id) == 'done':
                return
            visited[node_id] = 'visiting'
            path.append(node_id)
            for edge in self.graph.outgoing(node_id):
                dfs(edge.target_id, path)
            path.pop()
            visited[node_id] = 'done'

        for node_id in self.graph._nodes:
            if node_id not in visited:
                dfs(node_id, [])
