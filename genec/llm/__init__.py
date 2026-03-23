"""LLM utilities for GenEC."""

from typing import Protocol, runtime_checkable

from .anthropic_client import (
    AnthropicClientWrapper,
    LLMConfig,
    LLMRequestFailed,
    LLMServiceUnavailable,
)


@runtime_checkable
class LLMProvider(Protocol):
    """Abstract interface for LLM providers.

    Any class that exposes an ``enabled`` property and a ``send_message``
    method with the signature below satisfies this protocol.
    ``AnthropicClientWrapper`` is the canonical implementation.
    """

    @property
    def enabled(self) -> bool: ...

    def send_message(
        self,
        prompt: str,
        *,
        model: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.2,
    ) -> str: ...


__all__ = [
    "AnthropicClientWrapper",
    "LLMConfig",
    "LLMProvider",
    "LLMRequestFailed",
    "LLMServiceUnavailable",
]
