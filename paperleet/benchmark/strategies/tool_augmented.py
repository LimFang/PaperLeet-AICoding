"""S2 tool-augmented single-prompt strategy."""
import hashlib
from .base import StrategyRequest, StrategyResult, _append_user_context, _provider_usage, _validate_single_prompt_messages


class ToolAugmentedSinglePrompt:
    """S2: one target-model completion with a precomputed evidence bundle."""

    strategy_id = "S2"

    def __init__(self, client):
        self.client = client

    def run(self, request: StrategyRequest) -> StrategyResult:
        _validate_single_prompt_messages(request.messages)
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
            metadata={
                "evidence_digest": "sha256:" + hashlib.sha256(request.evidence.content.encode("utf-8")).hexdigest(),
                "evidence_characters": len(request.evidence.content),
            },
        )
