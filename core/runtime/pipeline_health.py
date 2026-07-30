"""Pipeline Health Check — verify all modules loaded, graph valid, registries ready."""
import logging
from typing import Dict, Tuple, List
from core.graph.graph_validator import GraphValidator
from core.graph.knowledge_graph import KnowledgeGraph
from core.detectors.detector_registry import DetectorRegistry
from core.setup.setup_registry import SetupRegistry

log = logging.getLogger(__name__)


def run_health_check(
    graph: KnowledgeGraph,
    detector_registry: DetectorRegistry,
    setup_registry: SetupRegistry,
) -> Tuple[bool, List[str]]:
    issues = []

    # 1. modules loaded (import check done at import time — if we got here, ok)
    log.info("module loaded: OK")

    # 2. graph valid
    ok, errs = GraphValidator(graph).validate()
    if not ok:
        issues += [f"graph: {e}" for e in errs]
    else:
        log.info(f"graph valid: {graph.node_count} nodes, {graph.edge_count} edges")

    # 3. detector registry
    dets = detector_registry.list()
    if not dets:
        issues.append("detector_registry: empty")
    else:
        log.info(f"detector_registry: {len(dets)} detector(s)")
        for did in dets:
            d = detector_registry.get(did)
            if not d.health_check():
                issues.append(f"detector unhealthy: {did}")

    # 4. setup registry
    setups = setup_registry.list()
    if not setups:
        issues.append("setup_registry: empty")
    else:
        log.info(f"setup_registry: {len(setups)} setup(s)")

    ok = len(issues) == 0
    if ok:
        log.info("pipeline ready: ALL GREEN")
    else:
        log.warning(f"pipeline health issues: {issues}")
    return ok, issues
