"""PatternMatcher — evaluates RuleResults against PatternDefinition. Generic."""
from typing import Any, Dict, List, Set
from core.patterns.pattern_match import PatternMatch, MATCH, PARTIAL_MATCH, NO_MATCH
from core.patterns.pattern_definition import PatternDefinition
from core.rules.rule_result import RuleResult
from core.patterns.pattern_explainer import build_explanation


class PatternMatcher:
    def match(
        self,
        pattern: PatternDefinition,
        rule_results: Dict[str, RuleResult],
    ) -> PatternMatch:
        """
        rule_results: dict[rule_label → RuleResult]
        Matches pattern.required_rules against passed rule results.
        """
        matched, failed, trace = [], [], []

        for rule_label in pattern.required_rules:
            rr = rule_results.get(rule_label)
            if rr and rr.passed:
                matched.append(rule_label)
                trace.append(f"✓ {rule_label}")
            else:
                failed.append(rule_label)
                trace.append(f"✗ {rule_label} (missing or FAIL)")

        total = len(pattern.required_rules)
        score = len(matched) / total if total else 0.0

        if score == 1.0:
            status = MATCH
        elif score > 0.0:
            status = PARTIAL_MATCH
        else:
            status = NO_MATCH

        explanation = build_explanation(pattern.name, matched, failed, score)

        return PatternMatch(
            pattern_id=pattern.id,
            pattern_name=pattern.name,
            status=status,
            score=round(score, 4),
            matched_rules=matched,
            failed_rules=failed,
            explanation=explanation,
            dependency_trace=trace,
        )

    def match_all(
        self,
        patterns: List[PatternDefinition],
        rule_results: Dict[str, RuleResult],
    ) -> List[PatternMatch]:
        results = [self.match(p, rule_results) for p in patterns]
        results.sort(key=lambda m: (-int(m.status == MATCH), -m.score))
        return results
