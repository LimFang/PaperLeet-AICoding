import copy
import json
from pathlib import Path

import pytest

from paperleet.benchmark.evaluator import evaluate_task
from paperleet.benchmark.reports import validate_run_report
from paperleet.benchmark.runner import BenchmarkRunner
from paperleet.benchmark.strategies import (
    AgenticStrategy,
    BlackBoxSinglePrompt,
    StrategyRequest,
)
from paperleet.tasks.aicb9.registry import load_registry, task_root


class FakeClient:
    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def complete(self, messages, tools, max_tokens):
        self.calls.append({"messages": messages, "tools": tools, "max_tokens": max_tokens})
        return {
            "choices": [{"message": {"role": "assistant", "content": json.dumps(self.answer)}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 80},
        }


def _reference_a01():
    return json.loads((task_root() / "A01" / "reference_trace.json").read_text(encoding="utf-8"))


def test_generic_runner_executes_deterministic_task_and_builds_manifest():
    client = FakeClient(_reference_a01())
    runner = BenchmarkRunner({"S0": BlackBoxSinglePrompt(client)})
    request = StrategyRequest(messages=[
        {"role": "system", "content": "Return the requested JSON."},
        {"role": "user", "content": "Trace TinyCache."},
    ])
    report = runner.run(
        "A01", "S0", request,
        model_metadata={"provider": "fake-provider", "model": "fake-model"},
        seed=17,
    )

    validate_run_report(report)
    assert report["status"] == "succeeded"
    assert report["metrics"]["correctness"]["score"] == 100
    assert report["metrics"]["correctness"]["passed"] is True
    assert report["metrics"]["efficiency"]["input_tokens"] == 120
    assert report["metrics"]["efficiency"]["output_tokens"] == 80
    assert report["metrics"]["efficiency"]["estimated_input_tokens"] > 0
    assert report["metrics"]["efficiency"]["estimated_output_tokens"] > 0
    assert report["metrics"]["efficiency"]["cost_usd"] is None
    assert report["manifest"]["task_id"] == "A01"
    assert report["manifest"]["task_version"] == "1.0.0"
    assert report["manifest"]["fixture_digest"].startswith("git-tree-sha1:")
    assert report["manifest"]["provider"] == "fake-provider"
    assert report["manifest"]["model_id"] == "fake-model"
    assert report["manifest"]["strategy"] == "S0"
    assert report["manifest"]["seed"] == 17
    assert report["manifest"]["seed_applied"] is False
    assert report["manifest"]["prompt_hash"].startswith("sha256:")
    assert report["artifacts"]["output_digest"].startswith("sha256:")
    assert len(client.calls) == 1
    assert client.calls[0]["tools"] == []


def test_generic_runner_executes_mocked_c01_agentic_task():
    class FakeRunner:
        def run(self, instruction):
            assert "Required behavior" in instruction
            return {
                "task_id": "C01",
                "final_text": "Patched retry behavior.",
                "plan": {"root_cause": "transient errors become terminal"},
                "trace": [
                    {"tool": "run_public_tests", "arguments": {}, "result": {"returncode": 0, "output": "3 passed"}},
                    {"tool": "git_diff", "arguments": {}, "result": {"returncode": 0, "output": "diff --git a/src/worker.py"}},
                ],
                "budget": {
                    "api_calls": 2,
                    "tool_calls": 2,
                    "input_tokens": 300,
                    "output_tokens": 100,
                    "estimated_input_tokens": None,
                },
                "stopped_reason": None,
            }

    task = next(item for item in load_registry() if item["id"] == "C01")
    instruction = (task["directory"] / "statement.md").read_text(encoding="utf-8")
    request = StrategyRequest(instruction=instruction)
    runner = BenchmarkRunner({"S3": AgenticStrategy(FakeRunner())})
    report = runner.run(
        "C01", "S3", request,
        model_metadata={"provider": "fake-provider", "model": "fake-agent"},
    )

    validate_run_report(report)
    assert report["status"] == "succeeded"
    assert report["metrics"]["correctness"]["status"] == "unavailable"
    assert "hidden-test" in report["metrics"]["correctness"]["reason"]
    assert report["metrics"]["efficiency"]["api_calls"] == 2
    assert report["metrics"]["efficiency"]["tool_calls"] == 2
    assert report["artifacts"]["patch_digest"].startswith("sha256:")
    assert report["artifacts"]["trace_digest"].startswith("sha256:")
    assert report["artifacts"]["test_report_digest"].startswith("sha256:")
    assert report["manifest"]["tool_schema_hash"].startswith("sha256:")


def test_runner_rejects_strategy_not_declared_by_task():
    runner = BenchmarkRunner({})
    with pytest.raises(ValueError, match="not supported by task"):
        runner.run("B03", "S0", StrategyRequest(messages=[
            {"role": "user", "content": "Generate tests."}
        ]))


def test_runner_records_failed_strategy_without_leaking_exception_text():
    class FailingStrategy:
        strategy_id = "S0"

        def run(self, request):
            raise RuntimeError("private-token-must-not-enter-report")

    runner = BenchmarkRunner({"S0": FailingStrategy()})
    report = runner.run(
        "A01", "S0",
        StrategyRequest(messages=[{"role": "user", "content": "run"}]),
    )
    assert report["status"] == "failed"
    assert report["stop_reason"] == "RuntimeError"
    assert "private-token-must-not-enter-report" not in json.dumps(report)


def test_b01_evidence_precision_and_recall_are_reported_separately():
    task = next(item for item in load_registry() if item["id"] == "B01")
    answer = {
        "root_cause_id": "round_unit_price_before_quantity",
        "primary_file": "src/ministore/pricing.py",
        "affected_function": "calculate_total",
        "causal_order": [
            "multiply_unit_price_by_quantity", "apply_discount",
            "round_line_subtotal", "calculate_tax",
        ],
        "evidence_ids": ["pricing.calculate_total", "extra.unsupported"],
        "excluded_hypotheses": ["tax_rate_is_primary_cause"],
    }
    from paperleet.benchmark.strategies.base import StrategyResult
    metrics = evaluate_task(task, StrategyResult(strategy="S0", output=answer))
    assert metrics["reasoning"]["precision"] == 0.5
    assert metrics["reasoning"]["recall"] == 0.5


def test_report_validator_rejects_unversioned_cost():
    client = FakeClient(_reference_a01())
    report = BenchmarkRunner({"S0": BlackBoxSinglePrompt(client)}).run(
        "A01", "S0", StrategyRequest(messages=[{"role": "user", "content": "trace"}])
    )
    invalid = copy.deepcopy(report)
    invalid["manifest"]["usage"]["cost_usd"] = 0.01
    invalid["manifest"]["usage"]["price_table_version"] = None
    with pytest.raises(ValueError, match="versioned price table"):
        validate_run_report(invalid)


def test_report_schema_file_declares_required_dimensions():
    schema_path = Path(__file__).resolve().parents[2] / "paperleet" / "benchmark" / "schemas" / "run-result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == "1.0"
    assert "DETERMINISTIC" in schema["properties"]["manifest"]["properties"]["strategy"]["enum"]
    assert set(schema["properties"]["metrics"]["required"]) == {
        "correctness", "reasoning", "robustness", "efficiency", "maintainability"
    }
