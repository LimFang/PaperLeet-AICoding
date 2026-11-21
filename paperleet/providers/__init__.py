"""Provider integrations for PaperLeet benchmark runs."""
from .model_config import ModelConfig
from .openai_compatible import OpenAICompatibleClient

__all__ = ["ModelConfig", "OpenAICompatibleClient"]
