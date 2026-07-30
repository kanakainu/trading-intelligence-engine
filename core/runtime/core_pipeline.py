"""Core Pipeline — full TIE end-to-end orchestrator. No YAML outside loader."""
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.compiler.knowledge_loader import KnowledgeLoader, KnowledgeRegistry
from core.graph.graph_builder import GraphBuilder
from core.graph.knowledge_graph import KnowledgeGraph
from core.context.context_engine import ContextEngine
from core.context.context_model import MarketContext
from core.detectors.detector_engine import DetectorEngine
from core.detectors.detector_registry import DetectorRegistry
from core.facts.facts_engine import FactsEngine
from core.facts.factset import FactSet
from core.setup.setup_engine import SetupEngine
from core.setup.setup_registry import SetupRegistry
from core.setup.setup_result import SetupResult
from core.decision.decision_engine import DecisionEngine
from core.decision.decision import Decision
from core.explanation.explanation_engine import ExplanationEngine
from core.explanation.explanation_report import ExplanationReport
from core.relationships.relationship import Relationship

log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    context: Optional[MarketContext] = None
    factset: Optional[FactSet] = None
    setup_results: List[SetupResult] = field(default_factory=list)
    decisions: List[Decision] = field(default_factory=list)
    explanations: List[ExplanationReport] = field(default_factory=list)
    timings: Dict[str, float] = field(default_factory=dict)


class CorePipeline:
    """
    Single orchestrator for the full TIE pipeline.
    Never reads YAML directly — KnowledgeLoader owns that.
    """

    def __init__(
        self,
        knowledge_registry: KnowledgeRegistry,
        relationships: List[Relationship],
        detector_registry: DetectorRegistry,
        setup_registry: SetupRegistry,
    ):
        t0 = time.perf_counter()

        self.graph: KnowledgeGraph = GraphBuilder(knowledge_registry).build(relationships)
        self.context_engine = ContextEngine()
        self.detector_engine = DetectorEngine(detector_registry)
        self.facts_engine = FactsEngine()
        self.setup_engine = SetupEngine(setup_registry)
        self.decision_engine = DecisionEngine()
        self.explanation_engine = ExplanationEngine()

        self._startup_time = time.perf_counter() - t0
        log.info(f"CorePipeline ready in {self._startup_time*1000:.1f}ms")

    def run(self, market_data: Dict[str, Any]) -> PipelineResult:
        result = PipelineResult()

        def timed(label, fn):
            t = time.perf_counter()
            out = fn()
            result.timings[label] = round(time.perf_counter() - t, 4)
            return out

        result.context     = timed("context",     lambda: self.context_engine.build(market_data))
        facts_raw          = timed("detector",     lambda: self.detector_engine.run(result.context))
        result.factset     = timed("facts",        lambda: self.facts_engine.process(
                                    facts_raw,
                                    market=market_data.get("symbol", ""),
                                    timeframe=market_data.get("timeframe", "")))
        result.setup_results = timed("setup",      lambda: self.setup_engine.evaluate(result.factset))
        result.decisions     = timed("decision",   lambda: self.decision_engine.decide(result.setup_results))

        reports = []
        for sr, dec in zip(result.setup_results, result.decisions):
            rpt = timed("explanation", lambda s=sr, d=dec: self.explanation_engine.explain(result.factset, s, d))
            reports.append(rpt)
        result.explanations = reports

        result.timings["startup"] = round(self._startup_time, 4)
        log.info(f"Pipeline complete: {result.timings}")
        return result
