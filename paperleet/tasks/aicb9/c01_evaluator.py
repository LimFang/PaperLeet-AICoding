"""Public/local C01 scoring; trusted hidden-test results are intentionally excluded."""
from collections.abc import Mapping


def evaluate_c01_public(agent_report, *, rubric_version="1.1.0"):
    """Score locally observable C01 components without accepting Agent-supplied hidden scores."""
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
        "details": {"complete": plan_complete, "required_fields": list(required_plan)},
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
            tool_calls <= limits["max_tool_calls"]
            if type(tool_calls) is int and type(limits.get("max_tool_calls")) is int else None
        ),
        "input_tokens": (
            input_used <= limits["max_input_tokens"]
            if isinstance(input_used, (int, float)) and not isinstance(input_used, bool)
            and isinstance(limits.get("max_input_tokens"), (int, float)) else None
        ),
        "output_tokens": (
            output_used <= limits["max_output_tokens"]
            if isinstance(output_used, (int, float)) and not isinstance(output_used, bool)
            and isinstance(limits.get("max_output_tokens"), (int, float)) else None
        ),
        "wall_time": (
            wall_time <= limits["max_wall_seconds"]
            if isinstance(wall_time, (int, float)) and not isinstance(wall_time, bool)
            and isinstance(limits.get("max_wall_seconds"), (int, float)) else None
        ),
        "completed_without_budget_stop": (
            agent_report["stopped_reason"] is None
            if "stopped_reason" in agent_report else None
        ),
    }
    efficiency_measurable = all(value is not None for value in checks.values())
    efficiency_passed = efficiency_measurable and all(value is True for value in checks.values())
    efficiency_component = {
        "status": "available" if efficiency_measurable else "unavailable",
        "score": 10 if efficiency_passed else (0 if efficiency_measurable else None),
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
        or str(path).replace("\\", "/").split("/")[-1] in {"task.yaml", "registry.yaml"}
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
    available_components = [item for item in components.values() if item["status"] == "available"]
    return {
        "task_id": "C01",
        "rubric_version": rubric_version,
        "hidden_tests": {
            "status": "unavailable",
            "score": None,
            "max_score": 55,
            "source": "trusted_evaluator_only",
            "agent_claims_accepted": False,
        },
        "components": components,
        "public_local_score": {
            "earned_points": sum(item["score"] for item in available_components),
            "available_points": sum(item["max_score"] for item in available_components),
            "maximum_local_points": 45,
            "official_score": None,
            "official_max_score": 100,
            "normalized_score": None,
        },
    }
