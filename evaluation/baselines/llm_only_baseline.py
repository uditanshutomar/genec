"""LLM-Only baseline: sends entire class to Claude without graph analysis or clustering."""

import re
import xml.etree.ElementTree as ET
from types import SimpleNamespace

from genec.core.models import RefactoringSuggestion
from genec.llm import AnthropicClientWrapper, LLMConfig, LLMRequestFailed, LLMServiceUnavailable
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)

PROMPT_TEMPLATE = (
    "Analyze this Java class and identify Extract Class refactoring opportunities. "
    "For each opportunity, list the methods and fields that should be extracted together, "
    "suggest a class name, and provide a rationale. "
    "Output in XML format: "
    "<suggestions>"
    "<suggestion>"
    "<class_name>...</class_name>"
    "<methods>method1, method2</methods>"
    "<fields>field1</fields>"
    "<rationale>...</rationale>"
    "</suggestion>"
    "</suggestions>\n\n"
)


class LLMOnlyBaseline:
    """Baseline that relies solely on Claude to identify Extract Class opportunities."""

    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-20250514"):
        self.logger = get_logger(self.__class__.__name__)
        config = LLMConfig(model=model, max_prompt_chars=60_000)
        self.client = AnthropicClientWrapper(api_key=api_key, config=config)

    def analyze(self, class_file: str) -> list[RefactoringSuggestion]:
        """Read a Java file, ask Claude for Extract Class suggestions, return results."""
        try:
            with open(class_file, encoding="utf-8") as f:
                source_code = f.read()
        except OSError as e:
            self.logger.error("Failed to read %s: %s", class_file, e)
            return []

        prompt = PROMPT_TEMPLATE + source_code

        try:
            response = self.client.send_message(
                prompt, max_tokens=4000, temperature=0.3
            )
        except (LLMServiceUnavailable, LLMRequestFailed) as e:
            self.logger.error("LLM call failed: %s", e)
            return []

        return self._parse_response(response)

    def _parse_response(self, response: str) -> list[RefactoringSuggestion]:
        """Parse XML response from Claude into RefactoringSuggestion objects."""
        suggestions: list[RefactoringSuggestion] = []

        # Extract XML block from response (Claude may include surrounding text)
        xml_match = re.search(r"<suggestions>.*?</suggestions>", response, re.DOTALL)
        if not xml_match:
            self.logger.warning("No <suggestions> XML block found in LLM response")
            return []

        xml_text = xml_match.group(0)

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            self.logger.warning("Failed to parse XML response: %s", e)
            return []

        for idx, suggestion_el in enumerate(root.findall("suggestion")):
            try:
                class_name = (suggestion_el.findtext("class_name") or "").strip()
                methods_text = (suggestion_el.findtext("methods") or "").strip()
                fields_text = (suggestion_el.findtext("fields") or "").strip()
                rationale = (suggestion_el.findtext("rationale") or "").strip()

                methods = [m.strip() for m in methods_text.split(",") if m.strip()]
                fields = [f.strip() for f in fields_text.split(",") if f.strip()]

                if not class_name or not methods:
                    continue

                member_list = methods + fields
                cluster = SimpleNamespace(
                    id=idx,
                    member_names=member_list,
                    method_signatures=methods,
                    get_methods=lambda ml=methods: ml,
                )
                suggestions.append(
                    RefactoringSuggestion(
                        cluster_id=idx,
                        proposed_class_name=class_name,
                        rationale=rationale,
                        new_class_code="",
                        modified_original_code="",
                        cluster=cluster,
                    )
                )
            except Exception as e:
                self.logger.warning("Skipping malformed suggestion element: %s", e)

        self.logger.info("LLM-Only baseline produced %d suggestions", len(suggestions))
        return suggestions
