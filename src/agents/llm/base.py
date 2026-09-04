"""
Abstract LLM Provider
======================

Provider-agnostic interface for LLM interactions.

Design:
- All providers implement the same interface
- Structured output support (JSON mode)
- Token tracking and cost estimation
- Retry logic with exponential backoff
- Context window management

The LLM handles REASONING only:
- Market interpretation
- Hypothesis generation
- News analysis
- Coordination

Deterministic code handles:
- Risk calculations
- Position sizing
- Validation
- Execution
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMResponse:
    """Structured response from an LLM provider."""
    content: str
    structured_output: dict[str, Any] | None = None
    model: str = ""
    tokens_used: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_estimate: float = 0.0
    latency_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "structured_output": self.structured_output,
            "model": self.model,
            "tokens_used": self.tokens_used,
            "cost_estimate": self.cost_estimate,
            "latency_ms": self.latency_ms,
        }


@dataclass
class LLMMessage:
    """A message in a conversation."""
    role: str   # "system" | "user" | "assistant"
    content: str


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'openai', 'gemini', 'ollama')."""
        ...

    @property
    @abstractmethod
    def model(self) -> str:
        """Model identifier."""
        ...

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> LLMResponse:
        """
        Generate a completion from the LLM.

        Args:
            messages: Conversation history
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum response tokens
            json_mode: If true, force JSON output

        Returns:
            LLMResponse with content and metadata
        """
        ...

    async def analyze(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        json_mode: bool = True,
    ) -> LLMResponse:
        """
        Convenience method for single-turn analysis.

        Used by agents for structured analysis tasks.
        """
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]
        return await self.complete(
            messages, temperature=temperature, json_mode=json_mode
        )

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available."""
        ...
