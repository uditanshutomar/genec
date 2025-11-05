"""
Shared Anthropic LLM client with retry/backoff and prompt trimming.

This wrapper centralises all Anthropic API usage so we can enforce
common safeguards: bounded prompt size, exponential backoff for
rate/overload responses, and graceful fallbacks when the service
is unavailable.
"""

from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass
from typing import Optional

import anthropic

from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


class LLMServiceUnavailable(Exception):
    """Raised when the LLM service is disabled or unavailable."""


class LLMRequestFailed(Exception):
    """Raised when an LLM request fails after retries."""


@dataclass
class LLMConfig:
    """Configuration for Anthropic client wrapper."""

    model: str = "claude-sonnet-4-20250514"
    max_prompt_chars: int = 16000
    max_retries: int = 3
    initial_backoff: float = 1.0  # seconds
    backoff_factor: float = 2.0
    max_backoff: float = 30.0
    timeout: Optional[float] = 60.0  # seconds


class AnthropicClientWrapper:
    """Centralised Anthropic messages client with retry/backoff."""

    def __init__(self, api_key: Optional[str] = None, config: Optional[LLMConfig] = None):
        self.logger = get_logger(self.__class__.__name__)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.config = config or LLMConfig()

        if not self.api_key:
            self.logger.warning("Anthropic API key not found; LLM features disabled.")
            self._enabled = False
            self._client = None
        else:
            self._enabled = True
            # Pass timeout to client if supported
            client_kwargs = {"api_key": self.api_key}
            if self.config.timeout is not None:
                client_kwargs["timeout"] = self.config.timeout
            self._client = anthropic.Anthropic(**client_kwargs)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def send_message(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.2,
    ) -> str:
        """
        Send a prompt to Anthropic with retries and prompt trimming.

        Returns:
            The response text (first content block) on success.

        Raises:
            LLMServiceUnavailable: if no API key was provided.
            LLMRequestFailed: if all retries fail.
        """
        if not self.enabled:
            raise LLMServiceUnavailable("Anthropic client disabled (no API key).")

        truncated_prompt = self._truncate_prompt(prompt)
        attempt = 0
        backoff = self.config.initial_backoff
        last_error: Optional[Exception] = None

        while attempt < self.config.max_retries:
            attempt += 1
            try:
                response = self._client.messages.create(
                    model=model or self.config.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[{"role": "user", "content": truncated_prompt}],
                )

                if not response.content:
                    raise LLMRequestFailed("Empty response content from Anthropic.")

                return response.content[0].text

            except anthropic.RateLimitError as err:
                last_error = err
                self._log_retry("Rate limit", attempt, backoff, err)
            except anthropic.APIStatusError as err:
                last_error = err
                status = getattr(err, "status_code", None)
                if status and status >= 500:
                    self._log_retry("Service error", attempt, backoff, err)
                else:
                    break
            except anthropic.APIError as err:
                last_error = err
                break
            except Exception as err:
                last_error = err
                self._log_retry("Unexpected error", attempt, backoff, err)

            # Apply exponential backoff with jitter before next retry
            sleep_time = min(backoff, self.config.max_backoff)
            sleep_time *= 1 + random.uniform(-0.1, 0.1)  # jitter ±10%
            time.sleep(max(sleep_time, 0))
            backoff *= self.config.backoff_factor

        error_message = f"Anthropic request failed after {attempt} attempts."
        if last_error:
            error_message += f" Last error: {last_error}"
        raise LLMRequestFailed(error_message)

    # --------------------------------------------------------------------- #
    # Helpers
    # --------------------------------------------------------------------- #
    def _truncate_prompt(self, prompt: str) -> str:
        if len(prompt) <= self.config.max_prompt_chars:
            return prompt

        truncated = prompt[: self.config.max_prompt_chars]
        self.logger.warning(
            "Prompt length %s exceeded limit (%s). Truncating.",
            len(prompt),
            self.config.max_prompt_chars,
        )
        return truncated

    def _log_retry(self, reason: str, attempt: int, backoff: float, exc: Exception) -> None:
        self.logger.warning(
            "Anthropic request attempt %s failed (%s). Retrying in %.2fs. Error: %s",
            attempt,
            reason,
            min(backoff, self.config.max_backoff),
            exc,
        )
