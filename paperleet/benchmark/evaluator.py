"""Task-aware deterministic evaluation for generic benchmark runs."""
import json
import re
from typing import Any, Mapping

from paperleet.tasks.aicb9.evaluators import evaluate_a01, evaluate_b01
from .metrics import evidence_metrics


def _response_content(output: Any) -> Any:
    if isinstance(output, Mapping):
        choices = output.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {}) if isinstance(choices[0], Mapping) else {}
            if isinstance(message, Mapping):
                return message.get("content")
        return output
    return output


def _parse_structured_output(output: Any) -> dict:
    content = _response_content(output)
    if isinstance(content, Mapping):
        return dict(content)
    if not isinstance(content, str):
        raise ValueError("model response did not contain structured JSON content")
    text = content.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("structured task output must be a JSON object")
    return parsed


def _unavailable(status: str, **fields) -> dict:
    return {"status": status, **fields}


def evaluate_task(task: Mapping[str, Any], strategy_result) -> dict:
    """Evaluate only task components with a real public evaluator implementation."""
    task_id = task["id"]
    if task_id in ("A01", "B01"):
        try:
            answer = _parse_structured_output(strategy_result.output)
            evaluation = evaluate_a01(answer) if task_id == "A01" else evaluate_b01(answer)
        except (ValueError, TypeError, json.JSONDecodeError):
            return {
                "correctness": _unavailable("invalid", score=None, max_score=100, passed=False),
                "reasoning": _unavailable("not_applicable"),
                "robustness": _unavailable("not_applicable"),
                "maintainability": _unavailable("not_applicable"),
            }
        reasoning = (
            evidence_metrics(evaluation["details"])
            if task_id == "B01"
            else _unavailable("not_applicable")
        )
        return {
            "correctness": {
                "status": "available",
                "score": evaluation["score"],
                "max_score": evaluation["max_score"],
                "passed": evaluation["passed"],
                "breakdown": evaluation["breakdown"],
                "details": evaluation["details"],
                "rubric_version": task.get("rubric_version"),
            },
            "reasoning": reasoning,
            "robustness": _unavailable("not_applicable"),
            "maintainability": _unavailable("not_applicable"),
        }

    if task_id == "C01":
        trace = strategy_result.trace
        public_test_runs = [
            item.get("result")
            for item in trace
            if item.get("tool") == "run_public_tests"
        ]
        return {
            "correctness": _unavailable(
                "unavailable",
                reason="trusted hidden-test evaluation is not implemented in the public/local runner",
                public_test_runs=public_test_runs,
            ),
            "reasoning": _unavailable("not_implemented"),
            "robustness": _unavailable("not_implemented"),
            "maintainability": _unavailable("not_implemented"),
        }

    raise ValueError(f"No generic benchmark evaluator is registered for task {task_id}")
