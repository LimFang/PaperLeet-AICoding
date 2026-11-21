import copy

import pytest

from paperleet.benchmark.strategies import (
    AgenticStrategy,
    BenchmarkStrategy,
    BlackBoxSinglePrompt,
    EvidenceBundle,
    StrategyRequest,
    ToolAugmentedSinglePrompt,
    WhiteBoxSinglePrompt,
)


class FakeClient:
    def __init__(self, response=None):
        self.response = response or {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
        self.calls = []

    def complete(self, messages, tools, max_tokens):
        self.calls.append({
            "messages": copy.deepcopy(messages),
            "tools": copy.deepcopy(tools),
            "max_tokens": max_tokens,
        })
        return copy.deepcopy(self.response)


@pytest.fixture
def base_messages():
    return [
        {"role": "system", "content": "You solve software engineering tasks."},
        {"role": "user", "content": "Find the defect and return JSON."},
    ]


def test_s0_is_one_call_without_tools_or_method_steps(base_messages):
    client = FakeClient({"choices": [{"message": {"content": "answer"}}]})
    request = StrategyRequest(messages=base_messages, max_output_tokens=321)
    result = BlackBoxSinglePrompt(client).run(request)
    assert len(client.calls) == 1
    assert client.calls[0]["tools"] == []
    assert client.calls[0]["max_tokens"] == 321
    assert client.calls[0]["messages"] == base_messages
    assert result.strategy == "S0"
    assert result.api_calls == 1
    assert result.usage is None


def test_s1_is_one_call_and_adds_only_method_steps(base_messages):
    response = {"choices": [{"message": {"content": "answer"}}], "usage": {"prompt_tokens": 9, "completion_tokens": 3}}
    client = FakeClient(response)
    request = StrategyRequest(messages=base_messages, method_steps="Inspect call sites, then check invariants.")
    result = WhiteBoxSinglePrompt(client).run(request)
    sent = client.calls[0]["messages"]
    assert len(client.calls) == 1
    assert client.calls[0]["tools"] == []
    assert sent[0] == base_messages[0]
    assert sent[1]["content"] == (
        base_messages[1]["content"]
        + "\n\nMethod steps:\nInspect call sites, then check invariants."
    )
    assert request.messages == tuple(base_messages)
    assert result.usage == {
        "input_tokens": 9, "output_tokens": 3, "source": "provider_reported"
    }


def test_s0_rejects_method_steps_and_s1_requires_them(base_messages):
    with pytest.raises(ValueError, match="does not accept method_steps"):
        BlackBoxSinglePrompt(FakeClient()).run(
            StrategyRequest(messages=base_messages, method_steps="use static analysis")
        )
    with pytest.raises(ValueError, match="requires non-empty method_steps"):
        WhiteBoxSinglePrompt(FakeClient()).run(StrategyRequest(messages=base_messages))


def test_s2_is_one_call_and_records_evidence_provenance(base_messages):
    client = FakeClient()
    evidence = EvidenceBundle(
        "worker.py: retry branch marks transient errors terminal",
        provenance=({"source": "static-index", "version": "2", "digest": "sha256:abc"},),
    )
    result = ToolAugmentedSinglePrompt(client).run(
        StrategyRequest(messages=base_messages, evidence=evidence)
    )
    assert len(client.calls) == 1
    assert client.calls[0]["tools"] == []
    assert client.calls[0]["messages"][0] == base_messages[0]
    assert client.calls[0]["messages"][1]["content"].endswith(
        "External evidence:\nworker.py: retry branch marks transient errors terminal"
    )
    assert result.strategy == "S2"
    assert result.api_calls == 1
    assert result.evidence_provenance == evidence.provenance


def test_s2_requires_evidence_and_rejects_method_steps(base_messages):
    with pytest.raises(ValueError, match="requires a precomputed evidence bundle"):
        ToolAugmentedSinglePrompt(FakeClient()).run(StrategyRequest(messages=base_messages))
    with pytest.raises(ValueError, match="does not accept method_steps"):
        ToolAugmentedSinglePrompt(FakeClient()).run(
            StrategyRequest(
                messages=base_messages,
                method_steps="inspect the control flow",
                evidence=EvidenceBundle("precomputed evidence"),
            )
        )


def test_strategy_result_serialization_contains_no_provider_configuration(base_messages):
    result = BlackBoxSinglePrompt(FakeClient()).run(StrategyRequest(messages=base_messages))
    serialized = repr(result.to_dict())
    assert "api_key" not in serialized
    assert "secret" not in serialized


def test_s3_wraps_existing_runner_and_preserves_trace_without_fake_zero_usage(base_messages):
    class FakeRunner:
        def __init__(self):
            self.instructions = []

        def run(self, instruction):
            self.instructions.append(instruction)
            return {
                "final_text": "patched",
                "trace": [{"tool": "read_file", "arguments": {"path": "src/a.py"}}],
                "budget": {
                    "api_calls": 2,
                    "tool_calls": 1,
                    "input_tokens": None,
                    "output_tokens": None,
                },
                "stopped_reason": None,
            }

    runner = FakeRunner()
    result = AgenticStrategy(runner).run(StrategyRequest(messages=base_messages))
    assert runner.instructions == [base_messages[-1]["content"]]
    assert result.strategy == "S3"
    assert result.api_calls == 2
    assert result.tool_calls == 1
    assert result.usage is None
    assert result.trace[0]["tool"] == "read_file"
    assert result.output["final_text"] == "patched"


def test_s3_accepts_explicit_instruction_and_reports_partial_usage():
    class FakeRunner:
        def run(self, instruction):
            assert instruction == "Fix the repository."
            return {
                "budget": {
                    "api_calls": 1,
                    "tool_calls": 0,
                    "input_tokens": 20,
                    "output_tokens": None,
                },
                "trace": [],
            }

    result = AgenticStrategy(FakeRunner()).run(
        StrategyRequest(instruction="Fix the repository.")
    )
    assert result.usage == {
        "input_tokens": 20, "output_tokens": None, "source": "provider_reported"
    }


def test_s3_requires_an_instruction():
    with pytest.raises(ValueError, match="requires a non-empty instruction"):
        AgenticStrategy(object()).run(StrategyRequest())


def test_all_adapters_implement_the_common_strategy_protocol(base_messages):
    client = FakeClient()
    class FakeRunner:
        def run(self, instruction):
            return {"budget": {}, "trace": []}

    adapters = [
        BlackBoxSinglePrompt(client),
        WhiteBoxSinglePrompt(client),
        ToolAugmentedSinglePrompt(client),
        AgenticStrategy(FakeRunner()),
    ]
    assert all(isinstance(adapter, BenchmarkStrategy) for adapter in adapters)
