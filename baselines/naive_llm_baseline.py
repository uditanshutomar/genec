"""Naive LLM baseline with minimal structural guidance."""

import os
import re
from typing import List, Optional
from dataclasses import dataclass

import anthropic

from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class NaiveLLMSuggestion:
    """Naive LLM baseline suggestion."""
    suggestion_text: str
    new_class_code: Optional[str] = None
    modified_original_code: Optional[str] = None


class NaiveLLMBaseline:
    """
    Naive LLM baseline approach.

    Direct prompt to LLM asking for Extract Class refactoring
    with minimal structural guidance.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = 'claude-sonnet-4-20250514',
        max_tokens: int = 4000
    ):
        """
        Initialize naive LLM baseline.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
            max_tokens: Maximum tokens
        """
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("Anthropic API key not provided")

        self.model = model
        self.max_tokens = max_tokens

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.logger = get_logger(self.__class__.__name__)

    def run(self, class_file: str) -> List[NaiveLLMSuggestion]:
        """
        Run naive LLM baseline on a class file.

        Args:
            class_file: Path to Java class file

        Returns:
            List of suggestions
        """
        self.logger.info(f"Running naive LLM baseline on {class_file}")

        # Read class file
        try:
            with open(class_file, 'r', encoding='utf-8') as f:
                class_code = f.read()
        except Exception as e:
            self.logger.error(f"Failed to read {class_file}: {e}")
            return []

        # Build simple prompt
        prompt = self._build_prompt(class_code)

        # Call LLM
        try:
            response = self._call_llm(prompt)
            if response:
                suggestion = NaiveLLMSuggestion(suggestion_text=response)

                # Try to extract code if present
                self._extract_code(suggestion)

                return [suggestion]
            else:
                return []

        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            return []

    def _build_prompt(self, class_code: str) -> str:
        """
        Build naive prompt.

        Args:
            class_code: Java class source code

        Returns:
            Prompt string
        """
        prompt = f"""Please refactor this Java class by applying the Extract Class refactoring pattern.

Identify opportunities to extract cohesive groups of methods and fields into new classes.

Here is the class:

```java
{class_code}
```

Provide your refactoring suggestions, including:
1. What to extract
2. Why it should be extracted
3. The refactored code for both the new class and modified original class

Format your response clearly."""

        return prompt

    def _call_llm(self, prompt: str) -> Optional[str]:
        """
        Call LLM with prompt.

        Args:
            prompt: Prompt string

        Returns:
            Response text
        """
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0.3,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                timeout=120
            )

            if message.content and len(message.content) > 0:
                return message.content[0].text

            return None

        except Exception as e:
            self.logger.error(f"LLM API error: {e}")
            raise

    def _extract_code(self, suggestion: NaiveLLMSuggestion):
        """
        Try to extract code blocks from suggestion text.

        Args:
            suggestion: Suggestion to update
        """
        # Look for code blocks
        code_blocks = re.findall(r'```java\s*\n(.*?)```', suggestion.suggestion_text, re.DOTALL)

        if len(code_blocks) >= 2:
            # Assume first is new class, second is modified original
            suggestion.new_class_code = code_blocks[0].strip()
            suggestion.modified_original_code = code_blocks[1].strip()
        elif len(code_blocks) == 1:
            suggestion.new_class_code = code_blocks[0].strip()
