"""Shared request/result contracts for benchmark strategies."""
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class EvidenceBundle:
    """Precomputed evidence supplied to S2, with source provenance."""

    content: str
    provenance: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self):
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("evidence content must be a non-empty string")
        object.__setattr__(self, "provenance", tuple(dict(item) for item in self.provenance))


@dataclass(frozen=True)
class StrategyRequest:
    """Input shared by one-shot and agentic strategy adapters."""

    messages: Sequence[Mapping[str, Any]] = ()
    max_output_tokens: int = 2048
    method_steps: str | None = None
    evidence: EvidenceBundle | None = None
    instruction: str | None = None

    def __post_init__(self):
        if type(self.max_output_tokens) is not int or self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be a positive integer")
        copied = []
        for message in self.messages:
            if not isinstance(message, Mapping) or not isinstance(message.get("role"), str):
                raise ValueError("each message must have a string role")
            if not isinstance(message.get("content"), str):
                raise ValueError("each message must have string content")
            copied.append(dict(message))
        object.__setattr__(self, "messages", tuple(copied))
        if self.method_steps is not None and not isinstance(self.method_steps, str):
            raise ValueError("method_steps must be a string")
        if self.instruction is not None and not isinstance(self.instruction, str):
            raise ValueError("instruction must be a string")


@dataclass(frozen=True)
class StrategyResult:
    """Serializable result shared by all strategy adapters; contains no client/config."""

    strategy: str
    output: Any
    usage: Mapping[str, Any] | None = None
    api_calls: int = 0
    tool_calls: int = 0
    evidence_provenance: tuple[Mapping[str, Any], ...] = ()
    trace: tuple[Mapping[str, Any], ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "output": self.output,
            "usage": dict(self.usage) if self.usage is not None else None,
            "api_calls": self.api_calls,
            "tool_calls": self.tool_calls,
            "evidence_provenance": [dict(item) for item in self.evidence_provenance],
            "trace": [dict(item) for item in self.trace],
            "metadata": dict(self.metadata),
        }



@runtime_checkable
class BenchmarkStrategy(Protocol):
    """Common execution interface implemented by every benchmark strategy."""

    strategy_id: str

    def run(self, request: StrategyRequest) -> StrategyResult:
        ...


def _prompt_hash(messages: Sequence[Mapping[str, Any]]) -> str:
    """Hash the canonical ordered messages sent to a single-prompt provider."""
    payload = json.dumps(list(messages), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_single_prompt_messages(messages: Sequence[Mapping[str, Any]]) -> None:
    if not messages:
        raise ValueError("single-prompt strategies require at least one message")
    for message in messages:
        if message.get("role") in ("tool", "function") or "tool_calls" in message or "tool_call_id" in message:
            raise ValueError("single-prompt strategies cannot include tool interaction history")


def _append_user_context(messages: Sequence[Mapping[str, Any]], heading: str, content: str) -> list[dict]:
    """Copy messages and append exactly one named context field to the last user message."""
    copied = [dict(message) for message in messages]
    for index in range(len(copied) - 1, -1, -1):
        if copied[index].get("role") == "user":
            previous = copied[index]["content"]
            copied[index]["content"] = f"{previous}\n\n{heading}:\n{content}"
            return copied
    copied.append({"role": "user", "content": f"{heading}:\n{content}"})
    return copied


def _provider_usage(response: Mapping[str, Any]) -> dict | None:
    raw = response.get("usage")
    if not isinstance(raw, Mapping):
        return None
    input_tokens = raw.get("prompt_tokens", raw.get("input_tokens"))
    output_tokens = raw.get("completion_tokens", raw.get("output_tokens"))
    if input_tokens is None and output_tokens is None:
        return None
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "source": "provider_reported",
    }
