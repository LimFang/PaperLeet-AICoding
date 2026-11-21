"""Run report construction, artifact digests, and schema validation."""
from datetime import datetime, timezone
import uuid
from typing import Any, Mapping

from .metrics import efficiency_metrics
from .protocol import (
    BENCHMARK_PROTOCOL_VERSION,
    OUTPUT_SCHEMA_VERSION,
    PROMPT_TEMPLATE_VERSION,
    RUN_REPORT_SCHEMA_VERSION,
    RUNNER_VERSION,
    STRATEGY_VERSION,
    RUN_STATUSES,
    sha256_digest,
)


METRIC_DIMENSIONS = ("correctness", "reasoning", "robustness", "efficiency", "maintainability")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _agent_trace(strategy_result) -> list:
    return list(strategy_result.trace or ())


def _artifact_digests(strategy_result) -> dict:
    output = strategy_result.output
    trace = _agent_trace(strategy_result)
    patch = None
    test_report = None
    for item in trace:
        tool = item.get("tool")
        result = item.get("result")
        if not isinstance(result, Mapping):
            continue
        if tool == "git_diff" and result.get("returncode") == 0:
            patch = result.get("output", "")
        elif tool == "run_public_tests":
            test_report = result
    return {
        "output_digest": sha256_digest(output),
        "patch_digest": sha256_digest(patch) if patch else None,
        "trace_digest": sha256_digest(trace) if trace else None,
        "test_report_digest": sha256_digest(test_report) if test_report is not None else None,
    }


def build_run_report(
    *,
    task: Mapping[str, Any],
    strategy_result,
    metrics: Mapping[str, Any],
    status: str,
    started_at: str,
    finished_at: str,
    wall_time_seconds: float,
    request,
    model_metadata: Mapping[str, Any] | None = None,
    seed: int | None = None,
    stop_reason: str | None = None,
) -> dict:
    if status not in RUN_STATUSES:
        raise ValueError(f"Invalid run status: {status}")
    metadata = dict(model_metadata or {})
    usage = strategy_result.usage or {}
    agent_budget = {}
    if isinstance(strategy_result.output, Mapping):
        candidate = strategy_result.output.get("budget", {})
        if isinstance(candidate, Mapping):
            agent_budget = candidate
    task_budget = dict(task.get("budget_limits") or {})
    task_budget.setdefault("max_output_tokens", request.max_output_tokens)
    manifest = {
        "run_id": str(uuid.uuid4()),
        "created_at": started_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "task_id": task["id"],
        "task_version": task.get("task_version", "0.0.0"),
        "fixture_digest": (task.get("fixture") or {}).get("digest"),
        "repository_commit": None,
        "protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "evaluator_version": task.get("rubric_version", "0.0.0"),
        "rubric_version": task.get("rubric_version", "0.0.0"),
        "runner_version": RUNNER_VERSION,
        "provider": metadata.get("provider", "injected"),
        "model_id": metadata.get("model"),
        "strategy": strategy_result.strategy,
        "strategy_version": STRATEGY_VERSION,
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "prompt_hash": strategy_result.metadata.get("prompt_hash"),
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "tool_schema_hash": strategy_result.metadata.get("tool_schema_hash"),
        "seed": seed,
        "seed_applied": False,
        "model_parameters": {"max_output_tokens": request.max_output_tokens},
        "budget_limits": task_budget,
        "usage": {
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "estimated_input_tokens": agent_budget.get("estimated_input_tokens"),
            "usage_source": usage.get("source", "unavailable"),
            "api_calls": strategy_result.api_calls,
            "tool_calls": strategy_result.tool_calls,
            "wall_time_seconds": round(float(wall_time_seconds), 6),
            "cost_usd": None,
            "currency": "USD",
            "price_table_version": None,
        },
        "seed_status": "recorded_only_provider_seed_not_forwarded",
    }
    report = {
        "schema_version": RUN_REPORT_SCHEMA_VERSION,
        "status": status,
        "manifest": manifest,
        "metrics": {key: dict(metrics[key]) for key in METRIC_DIMENSIONS},
        "artifacts": _artifact_digests(strategy_result),
        "output": strategy_result.to_dict(),
        "stop_reason": stop_reason,
    }
    validate_run_report(report)
    return report


def validate_run_report(report: Any) -> None:
    """Validate the required versioned report contract without a third-party schema library."""
    if not isinstance(report, dict):
        raise ValueError("run report must be an object")
    required = {"schema_version", "status", "manifest", "metrics", "artifacts", "output", "stop_reason"}
    missing = required - set(report)
    if missing:
        raise ValueError(f"run report is missing fields: {sorted(missing)}")
    if report["schema_version"] != RUN_REPORT_SCHEMA_VERSION:
        raise ValueError("unsupported run report schema version")
    if report["status"] not in RUN_STATUSES:
        raise ValueError("invalid run status")
    manifest = report["manifest"]
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    manifest_required = {
        "run_id", "created_at", "started_at", "finished_at", "task_id", "task_version",
        "fixture_digest", "protocol_version", "evaluator_version", "rubric_version",
        "runner_version", "provider", "model_id", "strategy", "strategy_version",
        "prompt_template_version", "prompt_hash", "output_schema_version", "seed",
        "seed_applied", "model_parameters", "budget_limits", "usage",
    }
    missing_manifest = manifest_required - set(manifest)
    if missing_manifest:
        raise ValueError(f"manifest is missing fields: {sorted(missing_manifest)}")
    if not isinstance(manifest["run_id"], str) or not manifest["run_id"]:
        raise ValueError("manifest.run_id must be a non-empty string")
    if manifest["strategy"] not in ("S0", "S1", "S2", "S3"):
        raise ValueError("manifest.strategy is invalid")
    if manifest["prompt_hash"] is not None and not str(manifest["prompt_hash"]).startswith("sha256:"):
        raise ValueError("manifest.prompt_hash must be a SHA-256 digest or null")
    if manifest["fixture_digest"] is not None and not str(manifest["fixture_digest"]).startswith(("sha256:", "git-tree-sha1:")):
        raise ValueError("manifest.fixture_digest must be a content digest or null")
    usage = manifest["usage"]
    if not isinstance(usage, dict):
        raise ValueError("manifest.usage must be an object")
    for key in ("input_tokens", "output_tokens", "estimated_input_tokens", "cost_usd"):
        value = usage.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0):
            raise ValueError(f"manifest.usage.{key} must be non-negative or null")
    if usage.get("cost_usd") is not None and not usage.get("price_table_version"):
        raise ValueError("cost requires a versioned price table")
    for key in ("api_calls", "tool_calls"):
        value = usage.get(key)
        if type(value) is not int or value < 0:
            raise ValueError(f"manifest.usage.{key} must be a non-negative integer")
    for key in ("output_digest", "patch_digest", "trace_digest", "test_report_digest"):
        value = report["artifacts"].get(key)
        if value is not None and not str(value).startswith("sha256:"):
            raise ValueError(f"artifacts.{key} must be a SHA-256 digest or null")
    metrics = report["metrics"]
    if not isinstance(metrics, dict) or set(METRIC_DIMENSIONS) - set(metrics):
        raise ValueError("metrics must include all five reporting dimensions")
    valid_metric_statuses = {"available", "unavailable", "not_implemented", "not_applicable", "invalid"}
    for dimension in METRIC_DIMENSIONS:
        metric = metrics[dimension]
        if not isinstance(metric, dict) or metric.get("status") not in valid_metric_statuses:
            raise ValueError(f"metrics.{dimension}.status is invalid")
    artifacts = report["artifacts"]
    if not isinstance(artifacts, dict) or set(("output_digest", "patch_digest", "trace_digest", "test_report_digest")) - set(artifacts):
        raise ValueError("artifacts must include output/patch/trace/test-report digest fields")
