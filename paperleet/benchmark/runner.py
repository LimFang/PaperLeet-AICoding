"""Generic task/strategy runner for reproducible AICB-9 experiments."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Mapping

from paperleet.tasks.aicb9.registry import load_registry
from .evaluator import evaluate_task
from .metrics import efficiency_metrics
from .reports import build_run_report
from .strategies.base import StrategyRequest, StrategyResult


class BenchmarkRunner:
    """Execute one registered task/strategy pair and return a versioned report."""

    def __init__(self, strategies: Mapping[str, Any], tasks=None):
        self.strategies = dict(strategies)
        self.tasks = list(tasks if tasks is not None else load_registry())
        self.tasks_by_id = {task["id"]: task for task in self.tasks}

    def get_task(self, identifier: str | int) -> dict:
        for task in self.tasks:
            if identifier in (task["id"], task.get("slug"), task.get("number")):
                return task
        raise ValueError(f"Unknown benchmark task {identifier!r}")

    def run(
        self,
        task_id: str | int,
        strategy_id: str,
        request: StrategyRequest,
        *,
        model_metadata: Mapping[str, Any] | None = None,
        seed: int | None = None,
    ) -> dict:
        task = self.get_task(task_id)
        strategy_id = str(strategy_id).upper()
        supported = (task.get("strategies") or {}).get("supported", [])
        if strategy_id not in supported:
            raise ValueError(
                f"Strategy {strategy_id} is not supported by task {task['id']}; "
                f"supported strategies: {', '.join(supported) or 'none'}"
            )
        if strategy_id not in self.strategies:
            raise ValueError(f"No strategy adapter registered for {strategy_id}")
        if seed is not None and type(seed) is not int:
            raise ValueError("seed must be an integer or null")

        started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        started = time.monotonic()
        strategy_result = None
        status = "succeeded"
        stop_reason = None
        try:
            strategy_result = self.strategies[strategy_id].run(request)
            if not isinstance(strategy_result, StrategyResult):
                raise TypeError("strategy adapter must return StrategyResult")
            if strategy_result.strategy != strategy_id:
                raise ValueError("strategy result ID does not match the requested strategy")
            task_metrics = evaluate_task(task, strategy_result)
        except Exception as exc:
            status = "failed"
            stop_reason = type(exc).__name__
            if not isinstance(strategy_result, StrategyResult):
                strategy_result = StrategyResult(
                    strategy=strategy_id,
                    output={"error_type": type(exc).__name__},
                )
            task_metrics = {
                "correctness": {"status": "invalid", "score": None, "passed": False},
                "reasoning": {"status": "unavailable"},
                "robustness": {"status": "unavailable"},
                "maintainability": {"status": "unavailable"},
            }

        wall_time = time.monotonic() - started
        if stop_reason is None:
            stop_reason = strategy_result.metadata.get("stop_reason")
        if status == "succeeded" and stop_reason:
            lowered = stop_reason.casefold()
            if "wall-clock" in lowered or "timeout" in lowered:
                status = "timed_out"
            elif "budget exceeded" in lowered or "budget" in lowered:
                status = "budget_exceeded"
            else:
                status = "failed"
        observed_efficiency = efficiency_metrics(strategy_result, wall_time)
        rubric_efficiency = task_metrics.get("efficiency", {})
        task_metrics["efficiency"] = {**observed_efficiency, **rubric_efficiency}
        finished_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return build_run_report(
            task=task,
            strategy_result=strategy_result,
            metrics=task_metrics,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            wall_time_seconds=wall_time,
            request=request,
            model_metadata=model_metadata,
            seed=seed,
            stop_reason=stop_reason,
        )

    def evaluate(self, task_id: str | int, answer) -> dict:
        """Score an existing structured answer locally without constructing a model client."""
        task = self.get_task(task_id)
        if task["id"] not in ("A01", "B01"):
            raise ValueError(f"Deterministic answer evaluation is not implemented for task {task['id']}")
        if isinstance(answer, (str, Path)):
            answer = json.loads(Path(answer).read_text(encoding="utf-8"))
        request = StrategyRequest(max_output_tokens=1)
        strategy_result = StrategyResult(strategy="DETERMINISTIC", output=answer)
        started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        started = time.monotonic()
        task_metrics = evaluate_task(task, strategy_result)
        wall_time = time.monotonic() - started
        task_metrics["efficiency"] = efficiency_metrics(strategy_result, wall_time)
        finished_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return build_run_report(
            task=task,
            strategy_result=strategy_result,
            metrics=task_metrics,
            status="succeeded",
            started_at=started_at,
            finished_at=finished_at,
            wall_time_seconds=wall_time,
            request=request,
            model_metadata={"provider": "local"},
            seed=None,
            stop_reason=None,
        )
