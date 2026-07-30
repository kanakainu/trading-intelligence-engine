"""Rule Engine — evaluate RuleObject against FactSet. Short-circuit, trace."""
from typing import Any, Dict, List
from core.rules.rule import AtomicRule, CompoundRule
from core.rules.rule_result import RuleResult
from core.rules.explanation import Explanation
from core.rules.evaluator import evaluate_atomic


class RuleEngine:
    def evaluate(self, rule: Any, facts: Dict[str, Any]) -> RuleResult:
        exp = Explanation()
        trace: List[str] = []
        matched: List[str] = []
        failed:  List[str] = []

        passed = self._eval(rule, facts, exp, trace, matched, failed)
        return RuleResult(
            passed=passed,
            matched=matched,
            failed=failed,
            explanation=exp.build(),
            trace=trace,
        )

    def _eval(self, rule: Any, facts: Dict[str, Any],
              exp: Explanation, trace: List[str],
              matched: List[str], failed: List[str]) -> bool:

        if isinstance(rule, AtomicRule):
            ok = evaluate_atomic(rule.fact, rule.op, rule.value, facts)
            label = repr(rule)
            exp.add(label, ok)
            trace.append(f"ATOM {label} => {'PASS' if ok else 'FAIL'}")
            (matched if ok else failed).append(label)
            return ok

        if isinstance(rule, CompoundRule):
            logic = rule.logic.upper()

            if logic == "AND":
                result = True
                for child in rule.rules:
                    ok = self._eval(child, facts, exp, trace, matched, failed)
                    if not ok:
                        result = False  # no short-circuit: collect all failures
                trace.append(f"AND => {'PASS' if result else 'FAIL'}")
                return result

            if logic == "OR":
                result = False
                for child in rule.rules:
                    ok = self._eval(child, facts, exp, trace, matched, failed)
                    if ok:
                        result = True  # no short-circuit: collect all
                trace.append(f"OR => {'PASS' if result else 'FAIL'}")
                return result

            if logic == "NOT":
                inner = rule.rules[0] if rule.rules else None
                if inner is None:
                    return False
                ok = self._eval(inner, facts, exp, trace, matched, failed)
                result = not ok
                trace.append(f"NOT => {'PASS' if result else 'FAIL'}")
                return result

        raise ValueError(f"Unknown rule type: {type(rule)}")
