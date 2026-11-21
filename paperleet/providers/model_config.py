"""Non-secret model configuration for OpenAI-compatible providers."""
from dataclasses import dataclass, field
import math
import os
from typing import Mapping


@dataclass(frozen=True)
class ModelConfig:
    """Provider configuration; the API key is deliberately excluded from repr/metadata."""

    provider: str
    model: str
    base_url: str
    api_key: str = field(repr=False)
    timeout: float = 60.0

    def __post_init__(self):
        for name, value in (("provider", self.provider), ("model", self.model),
                            ("base_url", self.base_url), ("api_key", self.api_key)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if isinstance(self.timeout, bool) or not isinstance(self.timeout, (int, float)) or not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ValueError("timeout must be a positive finite number")

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
    ) -> "ModelConfig":
        env = os.environ if environ is None else environ
        resolved_key = api_key or env.get("AICB9_API_KEY") or env.get("DEEPSEEK_API_KEY")
        resolved_model = model or env.get("AICB9_MODEL")
        resolved_base_url = base_url or env.get("AICB9_BASE_URL") or "https://api.deepseek.com"
        provider = env.get("AICB9_PROVIDER") or "openai_compatible"
        if not resolved_key:
            raise ValueError("Set AICB9_API_KEY or DEEPSEEK_API_KEY before making a model request")
        if not resolved_model:
            raise ValueError("Set AICB9_MODEL to a model ID enabled for your API account")
        return cls(
            provider=provider,
            model=resolved_model,
            base_url=resolved_base_url.rstrip("/"),
            api_key=resolved_key,
            timeout=timeout,
        )

    def public_metadata(self) -> dict:
        """Return only non-secret fields suitable for run manifests."""
        return {
            "provider": self.provider,
            "model": self.model,
            "timeout_seconds": self.timeout,
        }
