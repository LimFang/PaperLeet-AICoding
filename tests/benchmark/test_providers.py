import io
import urllib.error

import pytest

from paperleet.providers import ModelConfig, OpenAICompatibleClient


def test_model_config_reads_compatible_environment_names():
    config = ModelConfig.from_env({
        "AICB9_API_KEY": "test-secret",
        "AICB9_MODEL": "unit-model",
        "AICB9_BASE_URL": "https://example.invalid/v1/",
        "AICB9_PROVIDER": "test-provider",
    })
    assert config.model == "unit-model"
    assert config.base_url == "https://example.invalid/v1"
    assert config.provider == "test-provider"
    assert "test-secret" not in repr(config)
    assert "api_key" not in config.public_metadata()
    assert "test-secret" not in repr(config.public_metadata())


def test_model_config_supports_legacy_deepseek_key():
    config = ModelConfig.from_env({
        "DEEPSEEK_API_KEY": "legacy-secret",
        "AICB9_MODEL": "deepseek-test",
    })
    assert config.model == "deepseek-test"
    assert config.base_url == "https://api.deepseek.com"


@pytest.mark.parametrize("env,expected", [
    ({"AICB9_MODEL": "m"}, "AICB9_API_KEY"),
    ({"AICB9_API_KEY": "k"}, "AICB9_MODEL"),
])
def test_model_config_requires_key_and_model(env, expected):
    with pytest.raises(ValueError, match=expected):
        ModelConfig.from_env(env)


def test_openai_compatible_client_omits_empty_tool_fields():
    captured = {}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self):
            return b'{"choices":[{"message":{"content":"ok"}}]}'

    def opener(request, timeout):
        captured["request"] = request
        captured["payload"] = __import__("json").loads(request.data.decode())
        captured["timeout"] = timeout
        return Response()

    config = ModelConfig("test", "model-x", "https://example.invalid", "secret-key", 9)
    client = OpenAICompatibleClient(config=config, opener=opener)
    response = client.complete([{"role": "user", "content": "hello"}], [], 64)
    assert response["choices"][0]["message"]["content"] == "ok"
    assert "tools" not in captured["payload"]
    assert "tool_choice" not in captured["payload"]
    assert captured["request"].get_header("Authorization") == "Bearer secret-key"
    assert captured["timeout"] == 9


def test_openai_compatible_client_preserves_c01_tool_request_shape():
    captured = {}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"choices":[{"message":{"content":"ok"}}]}'

    def opener(request, timeout):
        captured["payload"] = __import__("json").loads(request.data.decode())
        return Response()

    client = OpenAICompatibleClient(
        api_key="secret", model="model-x", base_url="https://example.invalid",
        opener=opener,
    )
    client.complete([{"role": "user", "content": "inspect"}], [{"type": "function"}], 128)
    assert captured["payload"]["tools"] == [{"type": "function"}]
    assert captured["payload"]["tool_choice"] == "auto"


def test_http_error_body_redacts_api_key():
    secret = "very-secret-token"
    error = urllib.error.HTTPError(
        "https://example.invalid/chat/completions", 401, "Unauthorized", {},
        io.BytesIO(f"authorization rejected: {secret}".encode()),
    )

    def opener(request, timeout):
        raise error

    client = OpenAICompatibleClient(
        api_key=secret, model="model-x", base_url="https://example.invalid",
        opener=opener,
    )
    with pytest.raises(RuntimeError) as raised:
        client.complete([{"role": "user", "content": "hello"}], [], 16)
    assert secret not in str(raised.value)
    assert "[REDACTED]" in str(raised.value)


def test_legacy_agent_import_resolves_to_extracted_provider():
    from paperleet.tasks.aicb9.agent import OpenAICompatibleClient as LegacyClient
    assert LegacyClient is OpenAICompatibleClient
