"""S3 adapter around the existing bounded C01 AgentRunner."""
from .base import StrategyRequest, StrategyResult


class AgenticStrategy:
    """S3: delegate to the existing bounded AgentRunner; do not create a new agent loop."""

    strategy_id = "S3"

    def __init__(self, runner):
        self.runner = runner

    def run(self, request: StrategyRequest) -> StrategyResult:
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
        input_tokens = budget.get("input_tokens")
        output_tokens = budget.get("output_tokens")
        usage = None
        if input_tokens is not None or output_tokens is not None:
            usage = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "source": "provider_reported",
            }
        return StrategyResult(
            strategy=self.strategy_id,
            output=report,
            usage=usage,
            api_calls=int(budget.get("api_calls") or 0),
            tool_calls=int(budget.get("tool_calls") or 0),
            trace=tuple(report.get("trace") or ()),
            metadata={"stop_reason": report.get("stopped_reason")},
        )
