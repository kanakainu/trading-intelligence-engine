"""Risk layer data models — shared across engine, policies, audit."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class RiskDecision:
    approved: bool = False
    score: float = 0.0
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    execution_id: str = ""
    policy_results: Dict[str, Any] = field(default_factory=dict)
    triggered_policy: Optional[str] = None


@dataclass
class RiskAuditRecord:
    execution_id: str = ""
    approved: bool = False
    score: float = 0.0
    triggered_policy: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskHealthReport:
    status: str = "UNKNOWN"
    enabled_policies: List[str] = field(default_factory=list)
    evaluations: int = 0
    rejection_rate: float = 0.0 # 0.0 to 1.0
    last_evaluation: Optional[datetime] = None
    error: Optional[str] = None
