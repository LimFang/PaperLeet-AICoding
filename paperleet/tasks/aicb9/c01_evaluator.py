"""Deterministic structured-answer evaluators for AICB-9 pilot tasks."""
import json
from pathlib import Path
from collections.abc import Mapping

from .registry import task_root


A01_STEP_FIELDS = {"step", "result", "expired", "lru", "evicted"}
A01_TOP_LEVEL_FIELDS = {"steps"}
A01_LIST_FIELDS = {"expired", "lru", "evicted"}
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
    if isinstance(answer, (str, Path)):
        return json.loads(Path(answer).read_text(encoding="utf-8"))
    raise ValueError("answer must be a JSON object or a path to a JSON file")


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
        details[field] = {
            "matched_steps": correct,
            "total_steps": total,
            "mismatches": [
                {
                    "step": expected["step"],
                    "expected": expected[field],
                    "actual": by_step.get(expected["step"], {}).get(field),
                    "present": field in by_step.get(expected["step"], {}),
                }
                for expected in reference
                if field not in by_step.get(expected["step"], {})
                or by_step[expected["step"]][field] != expected[field]
            ],
        }
    score = round(sum(breakdown.values()), 2)
    return {
        "task_id": "A01",
        "score": score,
        "max_score": 100,
        "passed": score >= 80,
        "breakdown": breakdown,
        "details": details,
        "validation": {
            "submitted_steps": len(by_step),
            "missing_steps": sorted(set(range(1, 7)) - set(by_step)),
        },
        "scoring_mode": "deterministic_rubric",
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
        "task_id": "B01",
        "score": score,
        "max_score": 100,
        "passed": score >= 80,
        "breakdown": breakdown,
        "details": {
            "primary_file": {
                "passed": actual["primary_file"] == expected["primary_file"],
                "expected": expected["primary_file"],
                "actual": actual["primary_file"],
                "present": "primary_file" in payload,
            },
            "root_cause_id": {
                "passed": actual["root_cause_id"] == expected["root_cause_id"],
                "expected": expected["root_cause_id"],
                "actual": actual["root_cause_id"],
                "present": "root_cause_id" in payload,
            },
            "affected_function": {
                "passed": actual["affected_function"] == expected["affected_function"],
                "expected": expected["affected_function"],
                "actual": actual["affected_function"],
                "present": "affected_function" in payload,
            },
            "causal_order": {
                "passed": actual["causal_order"] == expected["causal_order"],
                "expected": expected["causal_order"],
                "actual": actual["causal_order"],
                "present": "causal_order" in payload,
            },
            "evidence": {
                "required": sorted(gold_evidence),
                "provided": sorted(provided_evidence),
                "present": "evidence_ids" in payload,
                "known": sorted(provided_evidence & valid_evidence_ids),
                "unsupported": unsupported_evidence,
                "false_positive": sorted(provided_evidence - gold_evidence),
                "precision": round(evidence_precision, 6),
                "recall": round(evidence_recall, 6),
                "f1": round(evidence_f1, 6),
            },
            "alternative_hypothesis": {
                "required_exclusion": expected["excluded_hypotheses"][0],
                "passed": expected["excluded_hypotheses"][0] in actual["excluded_hypotheses"],
                "actual": actual["excluded_hypotheses"],
                "present": "excluded_hypotheses" in payload,
            },
        },
        "scoring_mode": "deterministic_rubric",
    }

def evaluate_c01_public(agent_report):
    """Score only locally verifiable C01 rubric components.

    The 55-point hidden-test component is always unavailable here. This function
    deliberately ignores any hidden-test score or claimed test result in model text.
    """
    if not isinstance(agent_report, Mapping):
        raise ValueError("C01 Agent report must be an object")

    plan = agent_report.get("plan")
    required_plan = ("root_cause", "affected_files", "expected_invariants", "test_plan", "risk_factors")
    plan_complete = (
        isinstance(plan, Mapping)
        and isinstance(plan.get("root_cause"), str)
        and bool(plan["root_cause"].strip())
        and all(
            isinstance(plan.get(key), list)
            and bool(plan[key])
            and all(isinstance(item, str) and item.strip() for item in plan[key])
            for key in required_plan[1:]
        )
    )
    plan_component = {
        "status": "available",
        "score": 15 if plan_complete else 0,
        "max_score": 15,
        "passed": plan_complete,
        "details": {
            "complete": plan_complete,
            "required_fields": list(required_plan),
        },
    }

    trace = agent_report.get("trace")
    trace = trace if isinstance(trace, list) else []
    public_test_runs = [
        item.get("result")
        for item in trace
        if isinstance(item, Mapping)
        and item.get("tool") == "run_public_tests"
        and isinstance(item.get("result"), Mapping)
    ]
    last_test = public_test_runs[-1] if public_test_runs else None
    tests_passed = (
        last_test is not None
        and type(last_test.get("returncode")) is int
        and last_test["returncode"] == 0
        and not last_test.get("timed_out", False)
    )
    verification_component = {
        "status": "available",
        "score": 15 if tests_passed else 0,
        "max_score": 15,
        "passed": tests_passed,
        "details": {
            "tests_run": bool(public_test_runs),
            "runs": [dict(item) for item in public_test_runs],
            "latest_returncode": last_test.get("returncode") if last_test else None,
        },
    }

    budget = agent_report.get("budget")
    budget = budget if isinstance(budget, Mapping) else {}
    limits = budget.get("limits")
    limits = limits if isinstance(limits, Mapping) else {}
    input_used = budget.get("input_tokens")
    if input_used is None:
        input_used = budget.get("estimated_input_tokens")
    output_used = budget.get("output_tokens")
    if output_used is None:
        output_used = budget.get("estimated_output_tokens")
    wall_time = budget.get("wall_time_s")
    tool_calls = budget.get("tool_calls")
    checks = {
        "tool_calls": (
            type(tool_calls) is int
            and type(limits.get("max_tool_calls")) is int
            and tool_calls <= limits["max_tool_calls"]
        ),
        "input_tokens": (
            isinstance(input_used, (int, float)) and not isinstance(input_used, bool)
            and isinstance(limits.get("max_input_tokens"), (int, float))
            and input_used <= limits["max_input_tokens"]
        ),
        "output_tokens": (
            isinstance(output_used, (int, float)) and not isinstance(output_used, bool)
            and isinstance(limits.get("max_output_tokens"), (int, float))
            and output_used <= limits["max_output_tokens"]
        ),
        "wall_time": (
            isinstance(wall_time, (int, float)) and not isinstance(wall_time, bool)
            and isinstance(limits.get("max_wall_seconds"), (int, float))
            and wall_time <= limits["max_wall_seconds"]
        ),
        "completed_without_budget_stop": agent_report.get("stopped_reason") is None,
    }
    efficiency_measurable = all(
        checks[key] is not None for key in checks
    )
    efficiency_passed = all(checks.values())
    efficiency_component = {
        "status": "available" if efficiency_measurable else "unavailable",
        "score": 10 if efficiency_measurable and efficiency_passed else (0 if efficiency_measurable else None),
        "max_score": 10,
        "passed": efficiency_passed if efficiency_measurable else None,
        "details": {
            "checks": checks,
            "input_usage_source": "provider" if budget.get("input_tokens") is not None else "estimated",
            "output_usage_source": "provider" if budget.get("output_tokens") is not None else "estimated",
            "stop_reason": agent_report.get("stopped_reason"),
        },
    }

    final_diff = agent_report.get("final_diff")
    changed_files = agent_report.get("changed_files")
    changed_files = changed_files if isinstance(changed_files, list) else []
    diff_check = agent_report.get("diff_check")
    diff_check = diff_check if isinstance(diff_check, Mapping) else {}
    protected_parts = {"tests", "hidden", "private", "reference", "mutants", "secrets"}
    protected_changes = [
        str(path) for path in changed_files
        if protected_parts.intersection(str(path).replace("\\", "/").split("/"))
        or str(path).split("/")[-1] in {"task.yaml", "registry.yaml"}
    ]
    snapshot_available = agent_report.get("snapshot_available") is True
    patch_present = isinstance(final_diff, str) and bool(final_diff.strip()) and bool(changed_files)
    patch_clean = type(diff_check.get("returncode")) is int and diff_check.get("returncode") == 0
    patch_passed = snapshot_available and patch_present and patch_clean and not protected_changes
    patch_component = {
        "status": "available" if snapshot_available else "unavailable",
        "score": 5 if patch_passed else (0 if snapshot_available else None),
        "max_score": 5,
        "passed": patch_passed if snapshot_available else None,
        "details": {
            "patch_present": patch_present,
            "changed_files": [str(path) for path in changed_files],
            "diff_check_returncode": diff_check.get("returncode"),
            "protected_changes": protected_changes,
        },
    }

    components = {
        "pre_edit_plan": plan_component,
        "verification": verification_component,
        "efficiency": efficiency_component,
        "patch_quality": patch_component,
    }
    available_components = [
        item for item in components.values() if item["status"] == "available"
    ]
    earned_points = sum(item["score"] for item in available_components)
    available_points = sum(item["max_score"] for item in available_components)
    return {
        "task_id": "C01",
        "rubric_version": "1.1.0",
        "hidden_tests": {
            "status": "unavailable",
            "score": None,
            "max_score": 55,
            "source": "trusted_evaluator_only",
            "agent_claims_accepted": False,
        },
        "components": components,
        "public_local_score": {
            "earned_points": earned_points,
            "available_points": available_points,
            "maximum_local_points": 45,
            "official_score": None,
            "official_max_score": 100,
            "normalized_score": None,
        },
    }
