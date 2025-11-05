"""
LLM-powered pattern transformer for enabling complex extractions.

Uses an LLM to suggest and apply design pattern transformations that enable
extractions that would otherwise be impossible (e.g., Strategy pattern for
abstract method dependencies, Visitor pattern for inner class access).
"""

from typing import List, Dict, Optional
from dataclasses import dataclass

from genec.core.cluster_detector import Cluster
from genec.core.dependency_analyzer import ClassDependencies
from genec.llm import (
    AnthropicClientWrapper,
    LLMRequestFailed,
    LLMServiceUnavailable,
)
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class TransformationStrategy:
    """Describes a pattern transformation to enable extraction."""
    pattern_name: str  # e.g., "Strategy", "Template Method", "Callback"
    description: str
    modifications_needed: List[str]
    confidence: float  # 0.0 to 1.0
    code_changes: Optional[Dict[str, str]] = None  # file -> suggested code


class LLMPatternTransformer:
    """Uses LLM to suggest design pattern transformations for complex extractions."""

    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize pattern transformer.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
        """
        self.logger = get_logger(self.__class__.__name__)
        self.llm = AnthropicClientWrapper(api_key=api_key)
        self.model = model
        self.enabled = self.llm.enabled

    def suggest_transformation(
        self,
        cluster: Cluster,
        class_deps: ClassDependencies,
        blocking_issues: List[str]
    ) -> Optional[TransformationStrategy]:
        """
        Use LLM to suggest design pattern transformations.

        Given extraction issues like:
        - Abstract method calls → Suggest Strategy/Template Method pattern
        - Inner class dependencies → Suggest extracting inner class or using interfaces
        - Complex state dependencies → Suggest Builder or Facade pattern

        Args:
            cluster: The cluster that cannot be extracted
            class_deps: Class dependencies
            blocking_issues: Issues preventing extraction

        Returns:
            TransformationStrategy if LLM finds a viable pattern, None otherwise
        """
        if not self.enabled:
            return None

        self.logger.info(f"Analyzing transformation patterns for cluster {cluster.id}")

        # Build context
        context = self._build_transformation_context(
            cluster, class_deps, blocking_issues
        )

        try:
            response_text = self.llm.send_message(
                context,
                model=self.model,
                max_tokens=4000,
                temperature=0.3,
            )

            strategy = self._parse_transformation_response(response_text)

            if strategy and strategy.confidence >= 0.6:
                self.logger.info(
                    f"Found transformation strategy: {strategy.pattern_name} "
                    f"(confidence: {strategy.confidence:.2f})"
                )
                return strategy
            else:
                self.logger.info("No viable transformation strategy found")
                return None

        except (LLMServiceUnavailable, LLMRequestFailed) as e:
            self.logger.error(f"Transformation analysis failed: {str(e)}")
            return None

    def _build_transformation_context(
        self,
        cluster: Cluster,
        class_deps: ClassDependencies,
        blocking_issues: List[str]
    ) -> str:
        """Build prompt for transformation analysis."""

        method_by_sig = {m.signature: m for m in class_deps.methods}
        cluster_methods = cluster.get_methods()

        # Get method details
        method_details = []
        for method_sig in cluster_methods[:8]:
            method_info = method_by_sig.get(method_sig)
            if method_info:
                modifiers = ', '.join(method_info.modifiers) if method_info.modifiers else 'none'
                body_preview = (method_info.body[:150] + '...') if method_info.body and len(method_info.body) > 150 else method_info.body or 'no body'
                method_details.append(
                    f"  {method_sig}\n"
                    f"    Modifiers: {modifiers}\n"
                    f"    Body: {body_preview}"
                )

        prompt = f"""You are a Java refactoring expert. Your task is to suggest design pattern transformations that would enable an otherwise impossible Extract Class refactoring.

**Original Class**: {class_deps.class_name} (package: {class_deps.package_name})

**Methods to Extract** ({len(cluster_methods)} methods):
{chr(10).join(method_details[:8])}
{'... and ' + str(len(cluster_methods) - 8) + ' more' if len(cluster_methods) > 8 else ''}

**Blocking Issues**:
{chr(10).join('- ' + issue for issue in blocking_issues)}

**Your Task**:
Suggest a design pattern transformation that would enable this extraction. Consider:

1. **For Abstract Method Dependencies**:
   - Strategy Pattern: Pass behavior as parameters
   - Template Method: Keep template in original, extract algorithm steps
   - Callback/Listener: Use interfaces to invert dependencies
   - Dependency Injection: Inject required behavior

2. **For Inner Class Dependencies**:
   - Extract Inner Class: Make it a top-level class
   - Interface Extraction: Use interfaces to break coupling
   - Visitor Pattern: Externalize operations on inner class

3. **For Complex State Dependencies**:
   - Facade Pattern: Provide simplified interface
   - Mediator Pattern: Coordinate between extracted and original
   - Observer Pattern: Decouple state changes

**Response Format**:
PATTERN: <pattern name>
CONFIDENCE: <0.0-1.0>
DESCRIPTION: <brief explanation of how this pattern solves the problem>
MODIFICATIONS:
1. <specific change needed>
2. <specific change needed>
...

CODE_CHANGES:
```java
// Show key code changes needed (interfaces, new classes, etc.)
// Keep it concise - show structure, not full implementation
```

Be practical: suggest patterns that are actually feasible and would result in clean, maintainable code.
Only suggest transformations with confidence >= 0.6.
"""
        return prompt

    def _parse_transformation_response(self, response_text: str) -> Optional[TransformationStrategy]:
        """Parse LLM response into transformation strategy."""
        lines = response_text.strip().split('\n')

        pattern_name = None
        confidence = 0.0
        description = ""
        modifications = []
        code_changes = {}

        in_modifications = False
        in_code = False
        current_code = []

        for line in lines:
            line_stripped = line.strip()

            if line_stripped.startswith('PATTERN:'):
                pattern_name = line_stripped.split(':', 1)[1].strip()
            elif line_stripped.startswith('CONFIDENCE:'):
                try:
                    confidence = float(line_stripped.split(':', 1)[1].strip())
                except:
                    confidence = 0.5
            elif line_stripped.startswith('DESCRIPTION:'):
                description = line_stripped.split(':', 1)[1].strip()
            elif line_stripped.startswith('MODIFICATIONS:'):
                in_modifications = True
                in_code = False
            elif line_stripped.startswith('CODE_CHANGES:'):
                in_modifications = False
                in_code = True
            elif in_modifications and line_stripped:
                # Parse modification list
                if line_stripped[0].isdigit() or line_stripped.startswith('-'):
                    mod = line_stripped.lstrip('0123456789.-) ').strip()
                    if mod:
                        modifications.append(mod)
            elif in_code:
                current_code.append(line)

        # Extract code changes
        if current_code:
            code_changes['transformation'] = '\n'.join(current_code)

        # Multi-line description capture
        if 'DESCRIPTION:' in response_text:
            desc_start = response_text.index('DESCRIPTION:') + len('DESCRIPTION:')
            desc_end = response_text.find('MODIFICATIONS:', desc_start)
            if desc_end == -1:
                desc_end = response_text.find('CODE_CHANGES:', desc_start)
            if desc_end == -1:
                desc_end = len(response_text)
            description = response_text[desc_start:desc_end].strip()

        if pattern_name and confidence >= 0.6:
            return TransformationStrategy(
                pattern_name=pattern_name,
                description=description,
                modifications_needed=modifications,
                confidence=confidence,
                code_changes=code_changes
            )

        return None

    def apply_transformation_guidance(
        self,
        strategy: TransformationStrategy,
        cluster: Cluster,
        class_deps: ClassDependencies
    ) -> str:
        """
        Generate guidance for applying the transformation.

        Returns a detailed explanation of how to apply the transformation.
        """
        guidance = f"""
╔═══════════════════════════════════════════════════════════════════════════╗
║ TRANSFORMATION GUIDANCE: {strategy.pattern_name}
║ Confidence: {strategy.confidence:.0%}
╚═══════════════════════════════════════════════════════════════════════════╝

{strategy.description}

REQUIRED MODIFICATIONS:
"""
        for i, mod in enumerate(strategy.modifications_needed, 1):
            guidance += f"  {i}. {mod}\n"

        if strategy.code_changes:
            guidance += "\nCODE STRUCTURE:\n"
            guidance += strategy.code_changes.get('transformation', '')

        guidance += f"""

NEXT STEPS:
1. Review the suggested transformation
2. Apply the pattern transformations to your codebase
3. Re-run GenEC to attempt extraction with the transformed code
4. The extraction should now succeed with proper design patterns in place

NOTE: This transformation will improve your code design even if you don't
      proceed with the extraction. The patterns suggested address real
      architectural issues in the current code.
"""
        return guidance
