"""Deterministic scoring for the structured AICB-9 pilot tasks."""
from pathlib import Path
import json
from .registry import task_root


def _read_answer(answer):
    if isinstance(answer, dict):
        return answer
    return json.loads(Path(answer).read_text(encoding="utf-8"))


def _result(task_id, breakdown, details):
    total = round(sum(breakdown.values()), 2)
    return {
        "task_id": task_id,
        "score": total,
        "max_score": 100,
        "passed": total >= 80,
        "breakdown": breakdown,
        "details": details,
        "scoring_mode": "deterministic_rubric",
    }


def evaluate_a01(answer):
    """Score a learner's six-step TinyCache execution trace."""
    payload = _read_answer(answer)
    expected_path = task_root() / "A01" / "reference_trace.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8"))["steps"]
    actual = payload.get("steps", [])
    if not isinstance(actual, list):
        actual = []
    actual_by_step = {row.get("step"): row for row in actual if isinstance(row, dict) and isinstance(row.get("step"), int)}
    fields = {
        "result": 40,
        "expired": 25,
        "lru": 20,
        "evicted": 15,
    }
    breakdown = {}
    details = {}
    for field, weight in fields.items():
        matches = 0
        mismatches = []
        for row in expected:
            got = actual_by_step.get(row["step"], {})
            if field in got and got[field] == row[field]:
                matches += 1
            else:
                mismatches.append({"step": row["step"], "expected": row[field], "actual": got.get(field)})
        breakdown[field] = round(weight * matches / len(expected), 2)
        details[field] = {"matched_steps": matches, "total_steps": len(expected), "mismatches": mismatches}
    return _result("A01", breakdown, details)


def evaluate_b01(answer):
    """Score a structured diagnosis of the MiniStore rounding defect."""
    payload = _read_answer(answer)
    breakdown = {}
    details = {}

    checks = {
        "primary_file": ("src/ministore/pricing.py", 20),
        "root_cause_id": ("round_unit_price_before_quantity", 30),
        "affected_function": ("calculate_total", 10),
    }
    for field, (expected, weight) in checks.items():
        ok = payload.get(field) == expected
        breakdown[field] = weight if ok else 0
        details[field] = {"passed": ok, "expected": expected, "actual": payload.get(field)}

    expected_order = [
        "multiply_unit_price_by_quantity",
        "apply_discount",
        "round_line_subtotal",
        "calculate_tax",
    ]
    got_order = payload.get("causal_order", [])
    order_ok = got_order == expected_order
    breakdown["causal_order"] = 20 if order_ok else 0
    details["causal_order"] = {"passed": order_ok, "expected": expected_order, "actual": got_order}

    required_evidence = {"pricing.calculate_total", "pricing.unit_rounding"}
    evidence = set(payload.get("evidence_ids", [])) if isinstance(payload.get("evidence_ids", []), list) else set()
    evidence_recall = len(required_evidence & evidence) / len(required_evidence)
    breakdown["evidence"] = round(15 * evidence_recall, 2)
    details["evidence"] = {"required": sorted(required_evidence), "provided": sorted(evidence), "recall": evidence_recall}

    excluded = set(payload.get("excluded_hypotheses", [])) if isinstance(payload.get("excluded_hypotheses", []), list) else set()
    excluded_ok = "tax_rate_is_primary_cause" in excluded
    breakdown["alternative_hypothesis"] = 5 if excluded_ok else 0
    details["alternative_hypothesis"] = {"required_exclusion": "tax_rate_is_primary_cause", "passed": excluded_ok}
    return _result("B01", breakdown, details)
