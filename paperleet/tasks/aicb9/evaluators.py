"""Deterministic structured-answer evaluators for AICB-9 pilot tasks."""
import json
from pathlib import Path
from collections.abc import Mapping

from .registry import task_root


A01_STEP_FIELDS = {"step", "result", "expired", "lru", "evicted"}
A01_TOP_LEVEL_FIELDS = {"steps"}
A01_LIST_FIELDS = {"expired", "lru", "evicted"}
A01_SCALAR_FIELDS = {"result"}
B01_TOP_LEVEL_FIELDS = {
    "root_cause_id",
    "primary_file",
    "affected_function",
    "causal_order",
    "evidence_ids",
    "excluded_hypotheses",
}
B01_LIST_FIELDS = {"causal_order", "evidence_ids", "excluded_hypotheses"}


def _read_answer(answer):
    if isinstance(answer, Mapping):
        return dict(answer)
    path = Path(answer)
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_top_level(payload, allowed, task_id):
    if not isinstance(payload, Mapping):
        raise ValueError(f"{task_id} answer must be a JSON object")
    extras = set(payload) - allowed
    if extras:
        raise ValueError(f"{task_id} answer contains unknown fields: {sorted(extras)}")


def _validate_string_list(value, label):
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a list of strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{label} must not contain duplicate values")


def evaluate_a01(answer):
    """Score a TinyCache trace; missing fields receive no credit, malformed fields are rejected.

    The expected step domain is exactly 1..6. Missing expected steps are valid partial
    submissions. Unknown/duplicate step IDs, unknown fields, and incorrect field types
    are invalid submissions and raise ValueError.
    """
    payload = _read_answer(answer)
    _validate_top_level(payload, A01_TOP_LEVEL_FIELDS, "A01")
    steps = payload.get("steps", [])
    if not isinstance(steps, list):
        raise ValueError("A01.steps must be a list")

    by_step = {}
    for row in steps:
        if not isinstance(row, Mapping):
            raise ValueError("A01 step entries must be objects")
        extras = set(row) - A01_STEP_FIELDS
        if extras:
            raise ValueError(f"A01 step contains unknown fields: {sorted(extras)}")
        step = row.get("step")
        if type(step) is not int:
            raise ValueError("A01 step.step must be an integer")
        if step not in range(1, 7):
            raise ValueError(f"A01 unknown step ID: {step}")
        if step in by_step:
            raise ValueError(f"A01 duplicate step ID: {step}")
        for field in A01_LIST_FIELDS:
            if field in row:
                _validate_string_list(row[field], f"A01 step {step}.{field}")
        if "result" in row and not (
            row["result"] is None or isinstance(row["result"], (str, int, float, bool))
        ):
            raise ValueError(f"A01 step {step}.result must be a JSON scalar or null")
        by_step[step] = dict(row)

    reference = json.loads((task_root() / "A01" / "reference_trace.json").read_text(encoding="utf-8"))["steps"]
    weights = {"result": 40, "expired": 25, "lru": 20, "evicted": 15}
    breakdown = {key: 0 for key in weights}
    details = {}
    for field, weight in weights.items():
        total = len(reference)
        correct = 0
        for expected in reference:
            actual = by_step.get(expected["step"], {})
            if field in actual and actual[field] == expected[field]:
                correct += 1
        breakdown[field] = round(weight * correct / total, 2)
        details[field] = {"correct": correct, "total": total}
    score = round(sum(breakdown.values()), 2)
    return {
        "task": "A01",
        "score": score,
        "max_score": 100,
        "passed": score >= 90,
        "breakdown": breakdown,
        "details": details,
        "validation": {
            "submitted_steps": len(by_step),
            "missing_steps": sorted(set(range(1, 7)) - set(by_step)),
        },
    }


def evaluate_b01(answer):
    """Score MiniStore diagnosis with strict shape checks and evidence F1.

    Missing fields receive partial/no credit. Unknown top-level fields, wrong field
    types, and duplicate list entries are rejected. Unknown evidence IDs are retained
    as unsupported predictions and reduce evidence precision rather than being ignored.
    """
    payload = _read_answer(answer)
    _validate_top_level(payload, B01_TOP_LEVEL_FIELDS, "B01")
    for field in ("root_cause_id", "primary_file", "affected_function"):
        if field in payload and not isinstance(payload[field], str):
            raise ValueError(f"B01.{field} must be a string")
    for field in B01_LIST_FIELDS:
        if field in payload:
            _validate_string_list(payload[field], f"B01.{field}")

    catalog_path = task_root() / "B01" / "evidence_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if isinstance(catalog, Mapping):
        valid_evidence_ids = {key for key, value in catalog.items() if isinstance(key, str) and isinstance(value, str)}
    else:
        valid_evidence_ids = {
            item["id"] for item in catalog.get("evidence", [])
            if isinstance(item, Mapping) and isinstance(item.get("id"), str)
        }
    gold_evidence = {"pricing.calculate_total", "pricing.unit_rounding"}
    provided_evidence = set(payload.get("evidence_ids", []))
    matched_evidence = gold_evidence & provided_evidence
    unsupported_evidence = sorted(provided_evidence - valid_evidence_ids)
    evidence_precision = len(matched_evidence) / len(provided_evidence) if provided_evidence else 0.0
    evidence_recall = len(matched_evidence) / len(gold_evidence)
    evidence_f1 = (
        2 * evidence_precision * evidence_recall / (evidence_precision + evidence_recall)
        if evidence_precision + evidence_recall else 0.0
    )

    expected = {
        "root_cause_id": "round_unit_price_before_quantity",
        "primary_file": "src/ministore/pricing.py",
        "affected_function": "calculate_total",
        "causal_order": [
            "multiply_unit_price_by_quantity",
            "apply_discount",
            "round_line_subtotal",
            "calculate_tax",
        ],
        "excluded_hypotheses": ["tax_rate_is_primary_cause"],
    }
    weights = {
        "primary_file": 20,
        "root_cause_id": 30,
        "affected_function": 10,
        "causal_order": 20,
        "evidence": 15,
        "alternative_hypothesis": 5,
    }
    actual = {
        "primary_file": payload.get("primary_file"),
        "root_cause_id": payload.get("root_cause_id"),
        "affected_function": payload.get("affected_function"),
        "causal_order": payload.get("causal_order", []),
        "evidence_ids": payload.get("evidence_ids", []),
        "excluded_hypotheses": payload.get("excluded_hypotheses", []),
    }
    breakdown = {
        "primary_file": weights["primary_file"] if actual["primary_file"] == expected["primary_file"] else 0,
        "root_cause_id": weights["root_cause_id"] if actual["root_cause_id"] == expected["root_cause_id"] else 0,
        "affected_function": weights["affected_function"] if actual["affected_function"] == expected["affected_function"] else 0,
        "causal_order": weights["causal_order"] if actual["causal_order"] == expected["causal_order"] else 0,
        "evidence": round(weights["evidence"] * evidence_f1, 2),
        "alternative_hypothesis": (
            weights["alternative_hypothesis"]
            if expected["excluded_hypotheses"][0] in actual["excluded_hypotheses"] else 0
        ),
    }
    score = round(sum(breakdown.values()), 2)
    return {
        "task": "B01",
        "score": score,
        "max_score": 100,
        "passed": score >= 85,
        "breakdown": breakdown,
        "details": {
            "expected": expected,
            "actual": actual,
            "evidence": {
                "required": sorted(gold_evidence),
                "provided": sorted(provided_evidence),
                "known": sorted(provided_evidence & valid_evidence_ids),
                "unsupported": unsupported_evidence,
                "precision": round(evidence_precision, 6),
                "recall": round(evidence_recall, 6),
                "f1": round(evidence_f1, 6),
            },
        },
    }
