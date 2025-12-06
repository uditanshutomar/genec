"""
LLM-powered semantic validator for extraction feasibility.

Uses an LLM to analyze whether a cluster can be safely extracted by understanding
the semantic relationships between methods, abstract dependencies, and design patterns.
"""

from dataclasses import dataclass

from genec.core.cluster_detector import Cluster
from genec.core.dependency_analyzer import ClassDependencies
from genec.llm import AnthropicClientWrapper, LLMRequestFailed, LLMServiceUnavailable
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class SemanticValidationResult:
    """Result of LLM semantic validation."""

    is_valid: bool
    confidence: float  # 0.0 to 1.0
    reasoning: str
    suggested_modifications: list[str]


class LLMSemanticValidator:
    """Uses LLM to validate extraction feasibility with semantic understanding."""

    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize LLM validator.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Claude model to use
        """
        self.logger = get_logger(self.__class__.__name__)
        self.llm = AnthropicClientWrapper(api_key=api_key)
        self.model = model
        self.enabled = self.llm.enabled

    def validate_extraction_semantics(
        self, cluster: Cluster, class_deps: ClassDependencies, identified_issues: list[str]
    ) -> SemanticValidationResult:
        """
        Use LLM to analyze whether extraction is semantically valid despite identified issues.

        The LLM can determine:
        - Whether abstract method calls can be handled via delegation patterns
        - If inner classes can be made accessible
        - Whether the extraction makes semantic sense
        - Suggested modifications to make extraction valid

        Args:
            cluster: The cluster to validate
            class_deps: Class dependencies
            identified_issues: List of issues found by static analysis

        Returns:
            SemanticValidationResult with LLM's assessment
        """
        if not self.enabled:
            return SemanticValidationResult(
                is_valid=False,
                confidence=0.0,
                reasoning="LLM validation disabled - no API key",
                suggested_modifications=[],
            )

        # Build context for LLM
        context = self._build_validation_context(cluster, class_deps, identified_issues)

        # Query LLM
        try:
            response_text = self.llm.send_message(
                context,
                model=self.model,
                max_tokens=2000,
                temperature=0.2,  # Low temperature for consistent analysis
            )

            # Parse response
            result = self._parse_llm_response(response_text)

            self.logger.info(
                f"LLM validation for cluster {cluster.id}: "
                f"{'VALID' if result.is_valid else 'INVALID'} "
                f"(confidence: {result.confidence:.2f})"
            )

            return result

        except (LLMServiceUnavailable, LLMRequestFailed) as e:
            self.logger.error(f"LLM validation failed: {str(e)}")
            return SemanticValidationResult(
                is_valid=False,
                confidence=0.0,
                reasoning=f"LLM validation error: {str(e)}",
                suggested_modifications=[],
            )

    def _build_validation_context(
        self, cluster: Cluster, class_deps: ClassDependencies, identified_issues: list[str]
    ) -> str:
        """Build context prompt for LLM analysis."""

        # Get method information
        method_by_sig = {m.signature: m for m in class_deps.methods}
        cluster_methods = cluster.get_methods()

        # Build method details
        method_details = []
        for method_sig in cluster_methods[:10]:  # Limit to first 10 to avoid token limits
            method_info = method_by_sig.get(method_sig)
            if method_info:
                modifiers = ", ".join(method_info.modifiers) if method_info.modifiers else "none"
                body_preview = (
                    (method_info.body[:200] + "...")
                    if method_info.body and len(method_info.body) > 200
                    else method_info.body or "no body"
                )
                method_details.append(
                    f"  - {method_sig}\n"
                    f"    Modifiers: {modifiers}\n"
                    f"    Body preview: {body_preview}"
                )

        prompt = f"""You are analyzing whether a cluster of Java methods can be safely extracted from a class into a new class.

**Original Class**: {class_deps.class_name}
**Package**: {class_deps.package_name}

**Cluster to Extract** ({len(cluster_methods)} methods):
{chr(10).join(method_details[:10])}
{'... and ' + str(len(cluster_methods) - 10) + ' more methods' if len(cluster_methods) > 10 else ''}

**Static Analysis Issues Found**:
{chr(10).join('- ' + issue for issue in identified_issues) if identified_issues else '- No issues found'}

**Your Task**:
Analyze whether this extraction can be made valid by:
1. Understanding if abstract method calls can be handled via proper delegation
2. Determining if inner class references are actually problematic
3. Assessing the semantic coherence of the extraction
4. Identifying design patterns that could make this work

**Respond in this EXACT format**:
VALID: yes/no
CONFIDENCE: 0.0-1.0
REASONING: <your detailed reasoning>
MODIFICATIONS: <comma-separated list of suggested changes, or "none">

Be conservative: only mark as VALID if you're confident the extraction can work with reasonable modifications.
Consider Java's access control, inheritance, and composition patterns.
"""
        return prompt

    def _parse_llm_response(self, response_text: str) -> SemanticValidationResult:
        """Parse structured LLM response."""
        lines = response_text.strip().split("\n")

        is_valid = False
        confidence = 0.0
        reasoning = ""
        modifications = []

        for line in lines:
            line = line.strip()
            if line.startswith("VALID:"):
                is_valid = "yes" in line.lower()
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.split(":", 1)[1].strip())
                except:
                    confidence = 0.5
            elif line.startswith("REASONING:"):
                reasoning = line.split(":", 1)[1].strip()
            elif line.startswith("MODIFICATIONS:"):
                mods = line.split(":", 1)[1].strip()
                if mods.lower() != "none":
                    modifications = [m.strip() for m in mods.split(",")]

        # If reasoning spans multiple lines, capture it
        if "REASONING:" in response_text:
            reasoning_start = response_text.index("REASONING:") + len("REASONING:")
            reasoning_end = response_text.find("MODIFICATIONS:", reasoning_start)
            if reasoning_end == -1:
                reasoning_end = len(response_text)
            reasoning = response_text[reasoning_start:reasoning_end].strip()

        return SemanticValidationResult(
            is_valid=is_valid,
            confidence=confidence,
            reasoning=reasoning,
            suggested_modifications=modifications,
        )
