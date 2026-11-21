"""S2 tool-augmented single-prompt strategy."""
from .base import StrategyRequest, StrategyResult, _append_user_context, _provider_usage


class ToolAugmentedSinglePrompt:
    """S2: one target-model completion with a precomputed evidence bundle."""

    strategy_id = "S2"

    def __init__(self, client):
        self.client = client

    def run(self, request: StrategyRequest) -> StrategyResult:
        if request.evidence is None:
            raise ValueError("S2 requires a precomputed evidence bundle")
        if request.method_steps is not None:
            raise ValueError("S2 does not accept method_steps; use S1 for method knowledge")
        messages = _append_user_context(
            request.messages, "External evidence", request.evidence.content
        )
        response = self.client.complete(messages, [], request.max_output_tokens)
        return StrategyResult(
            strategy=self.strategy_id,
            output=response,
            usage=_provider_usage(response),
            api_calls=1,
            evidence_provenance=request.evidence.provenance,
        )
