"""Benchmark strategy interfaces and adapters."""
from .base import BenchmarkStrategy, EvidenceBundle, StrategyRequest, StrategyResult
from .single_prompt import BlackBoxSinglePrompt, WhiteBoxSinglePrompt
from .tool_augmented import ToolAugmentedSinglePrompt
from .agentic import AgenticStrategy

__all__ = [
    "BenchmarkStrategy",
    "EvidenceBundle",
    "StrategyRequest",
    "StrategyResult",
    "BlackBoxSinglePrompt",
    "WhiteBoxSinglePrompt",
    "ToolAugmentedSinglePrompt",
    "AgenticStrategy",
]
