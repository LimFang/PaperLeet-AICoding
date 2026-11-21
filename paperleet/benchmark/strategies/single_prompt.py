"""S0/S1 single-prompt strategies."""
from .base import StrategyRequest, StrategyResult, _append_user_context, _provider_usage, _validate_single_prompt_messages


class BlackBoxSinglePrompt:
    """S0: one completion with no prescribed method steps or tool definitions."""

    strategy_id = "S0"

    def __init__(self, client):
        self.client = client

    def run(self, request: StrategyRequest) -> StrategyResult:
        _validate_single_prompt_messages(request.messages)
        if request.method_steps is not None:
            raise ValueError("S0 does not accept method_steps")
        if request.evidence is not None:
            raise ValueError("S0 does not accept an external evidence bundle")
        response = self.client.complete(list(request.messages), [], request.max_output_tokens)
        return StrategyResult(
            strategy=self.strategy_id,
            output=response,
            usage=_provider_usage(response),
            api_calls=1,
        )


class WhiteBoxSinglePrompt:
    """S1: S0's prompt plus only the explicitly supplied method-steps field."""

    strategy_id = "S1"

    def __init__(self, client):
        self.client = client

    def run(self, request: StrategyRequest) -> StrategyResult:
        if not isinstance(request.method_steps, str) or not request.method_steps.strip():
            raise ValueError("S1 requires non-empty method_steps")
        if request.evidence is not None:
            raise ValueError("S1 does not accept an external evidence bundle")
        messages = _append_user_context(
            request.messages, "Method steps", request.method_steps
        )
        response = self.client.complete(messages, [], request.max_output_tokens)
        return StrategyResult(
            strategy=self.strategy_id,
            output=response,
            usage=_provider_usage(response),
            api_calls=1,
        )
