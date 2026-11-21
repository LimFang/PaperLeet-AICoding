"""Task-independent metric extraction for benchmark reports."""
from typing import Any, Mapping


def _agent_budget(result_output: Any) -> Mapping[str, Any]:
    if isinstance(result_output, Mapping):
        budget = result_output.get("budget", {})
        return budget if isinstance(budget, Mapping) else {}
    return {}


def efficiency_metrics(strategy_result, wall_time_seconds: float) -> dict:
    """Report observed usage separately from estimates; cost stays unavailable without pricing."""
    usage = strategy_result.usage or {}
    budget = _agent_budget(strategy_result.output)
    return {
        "status": "available",
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "estimated_input_tokens": (
            budget.get("estimated_input_tokens")
            if budget.get("estimated_input_tokens") is not None
            else strategy_result.metadata.get("estimated_input_tokens")
        ),
        "estimated_output_tokens": strategy_result.metadata.get("estimated_output_tokens"),
        "usage_source": usage.get("source", "unavailable"),
        "api_calls": strategy_result.api_calls,
        "tool_calls": strategy_result.tool_calls,
        "wall_time_seconds": round(float(wall_time_seconds), 6),
        "cost_usd": None,
        "price_table_version": None,
    }


def evidence_metrics(details: Mapping[str, Any]) -> dict:
    """Derive evidence precision/recall from the deterministic B01 evaluator details."""
    evidence = details.get("evidence", {})
    if not isinstance(evidence, Mapping):
        return {"status": "not_implemented", "precision": None, "recall": None}
    required = set(evidence.get("required") or [])
    provided = set(evidence.get("provided") or [])
    if not required:
        recall = None
    else:
        recall = len(required & provided) / len(required)
    if not provided:
        precision = None
    else:
        precision = len(required & provided) / len(provided)
    return {
        "status": "available",
        "precision": round(precision, 6) if precision is not None else None,
        "recall": round(recall, 6) if recall is not None else None,
        "gold_evidence_count": len(required),
        "predicted_evidence_count": len(provided),
    }
