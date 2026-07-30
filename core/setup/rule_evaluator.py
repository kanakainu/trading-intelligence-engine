"""Rule Evaluator — AND/OR/NOT nested logic over FactSet. No trading logic."""
from typing import Any, Dict, List, Tuple
from core.detectors.fact import Fact


FactIndex = Dict[str, Any]  # {fact_type: value}


def _build_index(facts: List[Fact]) -> FactIndex:
    return {f.fact_type: f.value for f in facts}


def evaluate_rule(rule: Dict, fact_index: FactIndex) -> Tuple[bool, str, List[str], List[str]]:
    """
    rule format:
      {op: "AND"|"OR"|"NOT", rules: [...]}           # compound
      {fact: "trend", op: "eq"|"neq", value: "bullish"}  # leaf

    returns: (result, label, matched, failed)
    """
    op = rule.get("op", "").upper()

    # ── leaf rule ────────────────────────────────────────────────────────
    if "fact" in rule:
        fact_type = rule["fact"]
        expected  = str(rule.get("value", ""))
        comparator = rule.get("op", "eq").lower()
        actual = fact_index.get(fact_type)
        label  = f"{fact_type} {comparator} {expected}"
        if actual is None:
            return False, label, [], [f"missing:{fact_type}"]
        result = (str(actual) == expected) if comparator == "eq" else (str(actual) != expected)
        return result, label, ([label] if result else []), ([] if result else [label])

    # ── AND ───────────────────────────────────────────────────────────────
    if op == "AND":
        matched, failed = [], []
        all_ok = True
        for child in rule.get("rules", []):
            ok, lbl, m, f = evaluate_rule(child, fact_index)
            matched += m
            if not ok:
                all_ok = False
                failed += f
        return all_ok, "AND", matched, failed

    # ── OR ────────────────────────────────────────────────────────────────
    if op == "OR":
        matched, failed = [], []
        for child in rule.get("rules", []):
            ok, lbl, m, f = evaluate_rule(child, fact_index)
            matched += m; failed += f
        return len(matched) > 0, "OR", matched, failed

    # ── NOT ───────────────────────────────────────────────────────────────
    if op == "NOT":
        inner = rule.get("rules", [{}])[0]
        ok, lbl, m, f = evaluate_rule(inner, fact_index)
        label = f"NOT({lbl})"
        return not ok, label, ([label] if not ok else []), ([] if not ok else [label])

    return False, "unknown_op", [], [f"unknown_op:{op}"]
