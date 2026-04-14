"""LLM-Only baseline: sends entire class to Claude without graph analysis or clustering.

This baseline demonstrates what happens when you ask an LLM to perform Extract Class
refactoring end-to-end, with no static analysis, clustering, or deterministic code
generation. It uses the same model (Claude Sonnet) as GenEC but gives the LLM full
responsibility for identifying method groups, naming classes, AND generating code.

The comparison against GenEC demonstrates the value of:
1. Hybrid dependency analysis + Leiden clustering (vs. LLM grouping alone)
2. JDT AST rewriting (vs. LLM code generation)
3. Multi-tier verification (applied to both for fair comparison)
"""

import re
import xml.etree.ElementTree as ET
from types import SimpleNamespace

from genec.core.models import RefactoringSuggestion
from genec.llm import AnthropicClientWrapper, LLMConfig, LLMRequestFailed, LLMServiceUnavailable
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are a Senior Java Architect specializing in Extract Class refactoring. "
    "You identify cohesive method groups in God Classes and produce complete, "
    "compilable Java code for the extracted class and modified original."
)

PROMPT_TEMPLATE = """Analyze this Java class and perform Extract Class refactoring.

For EACH extraction opportunity:
1. Identify methods and fields that form a cohesive responsibility
2. Suggest a descriptive UpperCamelCase class name (avoid generic suffixes like Helper, Manager, Utils, Handler, Processor, Service)
3. Provide a one-sentence rationale
4. Rate your confidence (0.0 to 1.0)
5. Generate the COMPLETE Java source code for the new extracted class (must compile independently)
6. Generate the COMPLETE modified original class (extracted members removed, delegation added)

Output in this XML format:
<suggestions>
<suggestion>
  <class_name>ProposedName</class_name>
  <methods>method1, method2, method3</methods>
  <fields>field1, field2</fields>
  <rationale>One sentence explaining why these belong together.</rationale>
  <confidence>0.85</confidence>
  <new_class_code>
// Complete Java source code for the extracted class
package ...;
public class ProposedName {
    ...
}
  </new_class_code>
  <modified_original_code>
// Complete modified original class with extractions removed
package ...;
public class OriginalName {
    ...
}
  </modified_original_code>
</suggestion>
</suggestions>

Constraints:
- Each extracted class must be compilable with correct imports and package declaration
- The modified original must maintain its public API through delegation
- Prefer fewer, high-quality extractions over many weak ones
- Each extraction should represent a single clear responsibility

Here is the Java class to refactor:

"""


class LLMOnlyBaseline:
    """Baseline that relies solely on Claude to identify and execute Extract Class."""

    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-20250514"):
        self.logger = get_logger(self.__class__.__name__)
        config = LLMConfig(model=model, max_prompt_chars=180_000)
        self.client = AnthropicClientWrapper(api_key=api_key, config=config)

    def analyze(self, class_file: str) -> list[RefactoringSuggestion]:
        """Read a Java file, ask Claude for full Extract Class refactoring, return results."""
        try:
            with open(class_file, encoding="utf-8") as f:
                source_code = f.read()
        except OSError as e:
            self.logger.error("Failed to read %s: %s", class_file, e)
            return []

        prompt = SYSTEM_PROMPT + "\n\n" + PROMPT_TEMPLATE + source_code

        try:
            response = self.client.send_message(
                prompt, max_tokens=16000, temperature=0.3
            )
        except (LLMServiceUnavailable, LLMRequestFailed) as e:
            self.logger.error("LLM call failed: %s", e)
            return []

        return self._parse_response(response)

    def _parse_response(self, response: str) -> list[RefactoringSuggestion]:
        """Parse XML response from Claude into RefactoringSuggestion objects."""
        suggestions: list[RefactoringSuggestion] = []

        # Extract code blocks first via regex (XML parsing breaks on Java generics)
        suggestion_blocks = re.findall(
            r"<suggestion>(.*?)</suggestion>", response, re.DOTALL
        )
        if not suggestion_blocks:
            self.logger.warning("No <suggestion> blocks found in LLM response")
            return []

        for idx, block in enumerate(suggestion_blocks):
            try:
                class_name = self._extract_tag(block, "class_name")
                methods_text = self._extract_tag(block, "methods")
                fields_text = self._extract_tag(block, "fields")
                rationale = self._extract_tag(block, "rationale")
                confidence_text = self._extract_tag(block, "confidence")
                new_class_code = self._extract_tag(block, "new_class_code")
                modified_original = self._extract_tag(block, "modified_original_code")

                methods = [m.strip() for m in methods_text.split(",") if m.strip()]
                fields = [f.strip() for f in fields_text.split(",") if f.strip()]

                if not class_name or not methods:
                    continue

                confidence = 0.0
                try:
                    confidence = float(confidence_text)
                except (ValueError, TypeError):
                    pass

                member_types = {}
                for m in methods:
                    member_types[m] = "method"
                for f in fields:
                    member_types[f] = "field"

                cluster = SimpleNamespace(
                    id=idx,
                    member_names=list(member_types.keys()),
                    member_types=member_types,
                    method_signatures=methods,
                    get_methods=lambda ml=methods: ml,
                    get_fields=lambda fl=fields: fl,
                )

                suggestions.append(
                    RefactoringSuggestion(
                        cluster_id=idx,
                        proposed_class_name=class_name,
                        rationale=rationale,
                        new_class_code=new_class_code,
                        modified_original_code=modified_original,
                        cluster=cluster,
                        confidence_score=confidence,
                    )
                )
            except Exception as e:
                self.logger.warning("Skipping malformed suggestion %d: %s", idx, e)

        self.logger.info("LLM-Only baseline produced %d suggestions", len(suggestions))
        return suggestions

    @staticmethod
    def _extract_tag(block: str, tag: str) -> str:
        """Extract content from an XML tag using regex (handles code with < > chars)."""
        match = re.search(
            rf"<{tag}>(.*?)</{tag}>", block, re.DOTALL
        )
        return match.group(1).strip() if match else ""
