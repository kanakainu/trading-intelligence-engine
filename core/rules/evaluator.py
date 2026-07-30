"""Evaluator — atomic rule evaluation against FactSet dict."""
from typing import Any, Dict
from core.rules.operator import Op


def coerce(a, b):
    """Try to cast b to type of a for numeric comparisons."""
    try:
        return type(a)(b)
    except (TypeError, ValueError):
        return b


def evaluate_atomic(fact: str, op: Op, value: Any, facts: Dict[str, Any]) -> bool:
    if op == Op.EXISTS:
        return fact in facts
    if op == Op.NOT_EXISTS:
        return fact not in facts

    actual = facts.get(fact)
    if actual is None:
        return False

    v = coerce(actual, value)

    if op == Op.EQ:        return actual == v
    if op == Op.NEQ:       return actual != v
    if op == Op.GT:        return actual > v
    if op == Op.GTE:       return actual >= v
    if op == Op.LT:        return actual < v
    if op == Op.LTE:       return actual <= v
    if op == Op.IN:        return actual in value
    if op == Op.NOT_IN:    return actual not in value
    if op == Op.BETWEEN:
        lo, hi = value
        return coerce(actual, lo) <= actual <= coerce(actual, hi)
    return False
