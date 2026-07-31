"""StrategyValidator — validates strategy before registration."""
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.strategy.base_strategy import BaseStrategy


@dataclass
class ValidationResult:
    valid: bool
    errors: List[str]
    warnings: List[str]


class StrategyValidator:
    """Validate strategy config, metadata, and lifecycle before registration."""

    def validate(self, strategy: "BaseStrategy") -> ValidationResult:
        errors, warnings = [], []

        # Config validation
        if not strategy.id:
            errors.append("strategy.id is empty")
        if not strategy.name:
            errors.append("strategy.name is empty")
        if not strategy.version:
            errors.append("strategy.version is empty")
        if not strategy.supported_symbols:
            warnings.append("supported_symbols empty — will run on all symbols")
        if not strategy.supported_timeframes:
            warnings.append("supported_timeframes empty — will run on all timeframes")

        # Priority range
        if not (0 <= strategy.priority <= 100):
            errors.append(f"priority {strategy.priority} out of range [0, 100]")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)
