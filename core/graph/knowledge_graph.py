"""Knowledge Graph — nodes + directed edges, no trading logic."""
import json
import logging
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple

log = logging.getLogger(__name__)


class Node:
    def __init__(self, obj_id: str, category: str, data: Any):
        self.id = obj_id
        self.category = category
        self.data = data

    def __repr__(self):
        return f"<Node {self.category}:{self.id}>"


class Edge:
    def __init__(self, source_id: str, target_id: str, rel_type: str, description: str = "", metadata: Dict = None):
        self.source_id = source_id
        self.target_id = target_id
        self.rel_type = rel_type
        self.description = description
        self.metadata = metadata or {}

    def __repr__(self):
        return f"<Edge {self.source_id} --[{self.rel_type}]--> {self.target_id}>"


class KnowledgeGraph:
    def __init__(self):
        self._nodes: Dict[str, Node] = {}
        self._out: Dict[str, List[Edge]] = defaultdict(list)   # outgoing edges per node
        self._in:  Dict[str, List[Edge]] = defaultdict(list)   # incoming edges per node

    # ── Node API ─────────────────────────────────────────────────────────────

    def add_node(self, node: Node) -> None:
        if node.id in self._nodes:
            log.warning(f"Node already exists, skipping: {node.id}")
            return
        self._nodes[node.id] = node
        log.debug(f"Node added: {node}")

    def remove_node(self, obj_id: str) -> None:
        if obj_id not in self._nodes:
            return
        # Remove all edges referencing this node
        self._out.pop(obj_id, None)
        self._in.pop(obj_id, None)
        for src, edges in list(self._out.items()):
            self._out[src] = [e for e in edges if e.target_id != obj_id]
        for tgt, edges in list(self._in.items()):
            self._in[tgt] = [e for e in edges if e.source_id != obj_id]
        del self._nodes[obj_id]
        log.debug(f"Node removed: {obj_id}")

    def find_node(self, obj_id: str) -> Optional[Node]:
        return self._nodes.get(obj_id)

    # ── Edge API ─────────────────────────────────────────────────────────────

    def add_edge(self, edge: Edge) -> bool:
        # Duplicate check
        for existing in self._out[edge.source_id]:
            if existing.target_id == edge.target_id and existing.rel_type == edge.rel_type:
                log.warning(f"Duplicate edge skipped: {edge}")
                return False
        self._out[edge.source_id].append(edge)
        self._in[edge.target_id].append(edge)
        log.debug(f"Edge added: {edge}")
        return True

    def remove_edge(self, source_id: str, target_id: str, rel_type: str) -> None:
        self._out[source_id] = [e for e in self._out[source_id]
                                 if not (e.target_id == target_id and e.rel_type == rel_type)]
        self._in[target_id]  = [e for e in self._in[target_id]
                                 if not (e.source_id == source_id and e.rel_type == rel_type)]

    def neighbors(self, obj_id: str) -> List[str]:
        """All directly connected node IDs (both directions)."""
        out = {e.target_id for e in self._out.get(obj_id, [])}
        inc = {e.source_id for e in self._in.get(obj_id, [])}
        return list(out | inc)

    def outgoing(self, obj_id: str) -> List[Edge]:
        return list(self._out.get(obj_id, []))

    def incoming(self, obj_id: str) -> List[Edge]:
        return list(self._in.get(obj_id, []))

    # ── Queries ───────────────────────────────────────────────────────────────

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return sum(len(v) for v in self._out.values())

    # ── JSON dump ────────────────────────────────────────────────────────────

    def to_dict(self) -> Dict:
        nodes = [{"id": n.id, "category": n.category} for n in self._nodes.values()]
        edges = []
        for edge_list in self._out.values():
            for e in edge_list:
                edges.append({
                    "source": e.source_id,
                    "target": e.target_id,
                    "type": e.rel_type,
                    "description": e.description,
                })
        return {"nodes": nodes, "edges": edges}

    def dump_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
