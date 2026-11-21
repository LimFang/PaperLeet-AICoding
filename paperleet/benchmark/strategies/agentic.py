"""S3 adapter around the existing bounded C01 AgentRunner."""
import hashlib
import json

from paperleet.tasks.aicb9.agent import AGENT_SYSTEM_PROMPT, TOOL_DEFINITIONS
from .base import StrategyRequest, StrategyResult, _prompt_hash, _estimate_tokens


class AgenticStrategy:
    """S3: delegate to the existing bounded AgentRunner; do not create a new agent loop."""

    strategy_id = "S3"

    def __init__(self, runner):
        self.runner = runner

    def run(self, request: StrategyRequest) -> StrategyResult:
        if request.method_steps is not None or request.evidence is not None:
            raise ValueError("S3 receives its workflow through the agent instruction, not S1/S2 fields")
        instruction = request.instruction
        if instruction is None:
            for message in reversed(request.messages):
                if message.get("role") == "user":
                    instruction = message["content"]
                    break
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError("S3 requires a non-empty instruction or user message")

        report = self.runner.run(instruction)
        budget = report.get("budget", {})
        prompt_messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": instruction},
        ]
        prompt_hash = _prompt_hash(prompt_messages)
        estimated_input_tokens = _estimate_tokens(prompt_messages)
        tool_schema = json.dumps(TOOL_DEFINITIONS, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        tool_schema_hash = "sha256:" + hashlib.sha256(tool_schema.encode("utf-8")).hexdigest()
        input_tokens = budget.get("input_tokens")
        output_tokens = budget.get("output_tokens")
        usage = None
        if (
            input_tokens is not None or output_tokens is not None
            or budget.get("cost_usd") is not None
        ):
            usage = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "source": "provider_reported",
                "cost_usd": budget.get("cost_usd"),
                "price_table_version": budget.get("price_table_version"),
            }
        return StrategyResult(
            strategy=self.strategy_id,
            output=report,
            usage=usage,
            api_calls=int(budget.get("api_calls") or 0),
            tool_calls=int(budget.get("tool_calls") or 0),
            trace=tuple(report.get("trace") or ()),
            metadata={
                "stop_reason": report.get("stopped_reason"),
                "prompt_hash": prompt_hash,
                "tool_schema_hash": tool_schema_hash,
                "estimated_input_tokens": budget.get("estimated_input_tokens", estimated_input_tokens),
                "estimated_output_tokens": budget.get("estimated_output_tokens"),
            },
        )
