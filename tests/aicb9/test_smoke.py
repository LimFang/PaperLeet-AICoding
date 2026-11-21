"""Explicit API smoke command tests; all requests use an injected fake client."""
import json

import pytest

from paperleet.providers import ModelConfig
from scripts import aicb9 as cli


class FakeSmokeClient:
    def __init__(self, content="PAPERLEET_SMOKE_OK", usage=None):
        self.content = content
        self.usage = usage
        self.calls = []

    def complete(self, messages, tools, max_tokens):
        self.calls.append((messages, tools, max_tokens))
        response = {
            "choices": [{"message": {"role": "assistant", "content": self.content}}],
        }
        if self.usage is not None:
            response["usage"] = self.usage
        return response


def test_smoke_requires_explicit_paid_api_confirmation(capsys):
    config_calls = []
    def config_factory(**kwargs):
        config_calls.append(kwargs)
        raise AssertionError("no API configuration should be read without confirmation")

    with pytest.raises(SystemExit) as exc:
        cli.main(["smoke", "--model", "fake-model"], config_factory=config_factory)
    assert exc.value.code == 2
    assert config_calls == []
    assert "confirm-paid-api" in capsys.readouterr().err


def test_smoke_uses_one_fake_request_and_never_serializes_api_key(capsys):
    config = ModelConfig(
        provider="test-provider",
        model="fake-model",
        base_url="https://example.invalid",
        api_key="must-not-appear-in-output",
    )
    client = FakeSmokeClient(
        usage={"prompt_tokens": 12, "completion_tokens": 4}
    )
    result = cli.main(
        ["smoke", "--model", "fake-model", "--confirm-paid-api"],
        client_factory=lambda config: client,
        config_factory=lambda **kwargs: config,
    )
    report = json.loads(capsys.readouterr().out)
    assert result == 0
    assert report["status"] == "succeeded"
    assert report["provider"] == "test-provider"
    assert report["model"] == "fake-model"
    assert report["api_calls"] == 1
    assert report["input_tokens"] == 12
    assert report["output_tokens"] == 4
    assert report["cost_usd"] is None
    assert len(client.calls) == 1
    assert client.calls[0][1] == []
    assert client.calls[0][2] == 32
    assert "must-not-appear-in-output" not in json.dumps(report)


def test_smoke_reports_missing_provider_usage_without_fabricating_tokens(capsys):
    config = ModelConfig("test-provider", "fake-model", "https://example.invalid", "secret")
    client = FakeSmokeClient(usage=None)
    result = cli.main(
        ["smoke", "--model", "fake-model", "--confirm-paid-api"],
        client_factory=lambda config: client,
        config_factory=lambda **kwargs: config,
    )
    report = json.loads(capsys.readouterr().out)
    assert result == 0
    assert report["usage_source"] == "unavailable"
    assert report["input_tokens"] is None
    assert report["output_tokens"] is None
