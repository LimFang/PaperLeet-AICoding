"""OpenAI-compatible chat-completions transport with secret-safe errors."""
import json
import urllib.error
import urllib.request

from .model_config import ModelConfig


class OpenAICompatibleClient:
    """Small injectable HTTP client; compatible with the existing C01 interface."""

    def __init__(
        self,
        api_key=None,
        model=None,
        base_url=None,
        timeout=60,
        opener=None,
        config: ModelConfig | None = None,
    ):
        if config is not None and any(value is not None for value in (api_key, model, base_url)):
            raise ValueError("Pass either config or api_key/model/base_url, not both")
        self.config = config or ModelConfig.from_env(
            api_key=api_key, model=model, base_url=base_url, timeout=timeout
        )
        self.model = self.config.model
        self.base_url = self.config.base_url
        self.timeout = self.config.timeout
        self._api_key = self.config.api_key
        self.opener = opener or urllib.request.urlopen

    def complete(self, messages, tools, max_tokens):
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": False,
        }
        # Do not send empty tool definitions or tool_choice to single-prompt calls.
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:2000]
            if self._api_key:
                body = body.replace(self._api_key, "[REDACTED]")
            raise RuntimeError(f"Model API returned HTTP {exc.code}: {body}") from exc
