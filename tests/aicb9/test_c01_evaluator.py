import pytest

from paperleet.tasks.aicb9.c01_evaluator import evaluate_c01_public


def _valid_agent_report():
    return {
        "task_id": "C01",
        "plan": {
            "root_cause": "TransientError is handled as terminal failure.",
            "affected_files": ["src/taskflow/worker.py"],
            "expected_invariants": ["PermanentError is never retried."],
            "test_plan": ["Run public tests."],
            "risk_factors": ["Duplicate terminal events."],
        },
        "trace": [
            {
                "tool": "run_public_tests",
                "result": {"returncode": 0, "output": "2 passed", "timed_out": False},
            }
        ],
        "final_diff": "diff --git a/src/taskflow/worker.py b/src/taskflow/worker.py\n+retry",
        "changed_files": ["src/taskflow/worker.py"],
        "diff_check": {"returncode": 0, "output": ""},
        "snapshot_available": True,
        "budget": {
            "api_calls": 2,
            "tool_calls": 1,
            "input_tokens": 300,
            "output_tokens": 100,
            "estimated_input_tokens": None,
            "estimated_output_tokens": None,
            "wall_time_s": 12.0,
            "limits": {
                "max_tool_calls": 24,
                "max_input_tokens": 40000,
                "max_output_tokens": 8000,
                "max_wall_seconds": 120,
            },
        },
        "stopped_reason": None,
        # Deliberately untrusted fields: the evaluator must ignore them.
        "hidden_test_score": 55,
        "hidden_tests": {"score": 55, "passed": True},
    }


def test_c01_public_rubric_awards_only_observable_45_points():
    result = evaluate_c01_public(_valid_agent_report())
    assert result["hidden_tests"]["status"] == "unavailable"
    assert result["hidden_tests"]["score"] is None
    assert result["hidden_tests"]["max_score"] == 55
    assert result["hidden_tests"]["agent_claims_accepted"] is False
    assert result["public_local_score"] == {
        "earned_points": 45,
        "available_points": 45,
        "maximum_local_points": 45,
        "official_score": None,
        "official_max_score": 100,
        "normalized_score": None,
    }


def test_c01_no_patch_receives_no_patch_quality_credit():
    report = _valid_agent_report()
    report["final_diff"] = ""
    report["changed_files"] = []
    result = evaluate_c01_public(report)
    assert result["components"]["patch_quality"]["score"] == 0
    assert result["public_local_score"]["earned_points"] == 40


def test_c01_failing_public_tests_receive_no_verification_credit():
    report = _valid_agent_report()
    report["trace"][0]["result"] = {
        "returncode": 1, "output": "1 failed", "timed_out": False
    }
    result = evaluate_c01_public(report)
    assert result["components"]["verification"]["score"] == 0
    assert result["public_local_score"]["earned_points"] == 30


def test_c01_budget_exhaustion_receives_no_efficiency_credit():
    report = _valid_agent_report()
    report["stopped_reason"] = "tool-call budget exceeded"
    result = evaluate_c01_public(report)
    assert result["components"]["efficiency"]["score"] == 0
    assert result["public_local_score"]["earned_points"] == 35


def test_c01_estimated_usage_can_verify_budget_without_fabricating_actual_tokens():
    report = _valid_agent_report()
    report["budget"]["input_tokens"] = None
    report["budget"]["output_tokens"] = None
    report["budget"]["estimated_input_tokens"] = 350
    report["budget"]["estimated_output_tokens"] = 120
    result = evaluate_c01_public(report)
    efficiency = result["components"]["efficiency"]
    assert efficiency["score"] == 10
    assert efficiency["details"]["input_usage_source"] == "estimated"
    assert efficiency["details"]["output_usage_source"] == "estimated"


def test_c01_unavailable_git_snapshot_does_not_renormalize_local_score():
    report = _valid_agent_report()
    report["snapshot_available"] = False
    result = evaluate_c01_public(report)
    assert result["components"]["patch_quality"]["status"] == "unavailable"
    assert result["public_local_score"]["available_points"] == 40
    assert result["public_local_score"]["maximum_local_points"] == 45
    assert result["public_local_score"]["normalized_score"] is None
