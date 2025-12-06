"""
Validates whether a cluster can be safely extracted.

This module checks for dependencies that would make an extraction invalid:
- Abstract method calls
- Private method calls to non-extracted methods
- Inner class references
- Instance method calls that can't be delegated
"""

import re
from dataclasses import dataclass

from genec.core.cluster_detector import Cluster
from genec.core.dependency_analyzer import ClassDependencies, MethodInfo
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationIssue:
    """Represents a problem that would prevent safe extraction."""

    severity: str  # 'error' or 'warning'
    issue_type: str
    description: str
    affected_method: str


class ExtractionValidator:
    """Validates whether a cluster extraction is safe and will compile in practice."""

    def __init__(self, auto_fix: bool = True, use_llm: bool = True, suggest_patterns: bool = True):
        """
        Initialize validator.

        Args:
            auto_fix: If True, attempt to fix issues by expanding cluster to include dependencies
            use_llm: If True, use LLM for semantic validation of borderline cases
            suggest_patterns: If True, use LLM to suggest pattern transformations for rejected extractions
        """
        self.logger = get_logger(self.__class__.__name__)
        self.auto_fix = auto_fix
        self.use_llm = use_llm
        self.suggest_patterns = suggest_patterns

        # Initialize LLM validator if enabled
        self.llm_validator = None
        if use_llm:
            try:
                from genec.verification.llm_semantic_validator import LLMSemanticValidator

                self.llm_validator = LLMSemanticValidator()
                if self.llm_validator.enabled:
                    self.logger.info("LLM semantic validation enabled")
            except Exception as e:
                self.logger.warning(f"Could not initialize LLM validator: {e}")

        # Initialize pattern transformer if enabled
        self.pattern_transformer = None
        if suggest_patterns:
            try:
                from genec.verification.llm_pattern_transformer import LLMPatternTransformer

                self.pattern_transformer = LLMPatternTransformer()
                if self.pattern_transformer.enabled:
                    self.logger.info("LLM pattern transformation suggestions enabled")
            except Exception as e:
                self.logger.warning(f"Could not initialize pattern transformer: {e}")

    def validate_extraction(
        self, cluster: Cluster, class_deps: ClassDependencies
    ) -> tuple[bool, list[ValidationIssue]]:
        """
        Validate if a cluster can be safely extracted.

        If auto_fix is enabled, attempts to fix issues by including missing dependencies.

        Returns:
            (is_valid, issues): True if extraction is safe, along with list of issues found
        """
        issues = []
        fixed_issues = []

        # Get cluster methods
        cluster_methods = set(cluster.get_methods())
        if not cluster_methods:
            return True, []

        # Build lookup maps
        method_by_sig = {m.signature: m for m in class_deps.methods}
        method_names = {m.name: m for m in class_deps.methods}
        abstract_methods = self._find_abstract_methods(class_deps)

        # Iterative validation: keep checking until no new methods are added
        max_iterations = 10  # Prevent infinite loops
        iteration = 0
        methods_added = True

        while methods_added and iteration < max_iterations:
            methods_added = False
            iteration += 1
            current_issues = []

            # Check each method in the cluster
            for method_sig in list(cluster_methods):
                method_info = method_by_sig.get(method_sig)
                if not method_info:
                    continue

                # Check for abstract method calls
                abstract_calls = self._find_abstract_method_calls(
                    method_info, abstract_methods, method_names
                )
                for abstract_method in abstract_calls:
                    current_issues.append(
                        ValidationIssue(
                            severity="error",
                            issue_type="abstract_method_call",
                            description=f"Calls abstract method '{abstract_method}' which cannot be accessed from extracted class",
                            affected_method=method_sig,
                        )
                    )

                # Check for private method calls to non-extracted methods
                private_calls = self._find_private_method_calls(
                    method_info, class_deps, cluster_methods, method_by_sig
                )

                # Try to auto-fix by including private methods
                if self.auto_fix and private_calls:
                    for private_method_name in private_calls:
                        # Find the signature of this private method
                        for method in class_deps.methods:
                            if method.name == private_method_name and "private" in [
                                m.lower() for m in method.modifiers
                            ]:
                                if method.signature not in cluster_methods:
                                    # Add to cluster
                                    cluster.member_names.append(method.signature)
                                    cluster.member_types[method.signature] = "method"
                                    cluster_methods.add(method.signature)
                                    fixed_issues.append(
                                        f"Auto-included private helper method '{private_method_name}'"
                                    )
                                    self.logger.debug(
                                        f"Auto-included private method: {private_method_name}"
                                    )
                                    methods_added = True
                                break
                        else:
                            # Couldn't find the method to include - still an error
                            current_issues.append(
                                ValidationIssue(
                                    severity="error",
                                    issue_type="private_method_call",
                                    description=f"Calls private method '{private_method_name}' which cannot be included",
                                    affected_method=method_sig,
                                )
                            )
                elif private_calls:
                    for private_method in private_calls:
                        current_issues.append(
                            ValidationIssue(
                                severity="error",
                                issue_type="private_method_call",
                                description=f"Calls private method '{private_method}' which is not included in extraction",
                                affected_method=method_sig,
                            )
                        )

                # Check for inner class references
                inner_class_refs = self._find_inner_class_references(method_info)
                for inner_class in inner_class_refs:
                    current_issues.append(
                        ValidationIssue(
                            severity="error",
                            issue_type="inner_class_reference",
                            description=f"References inner class '{inner_class}' which may not be accessible from extracted class",
                            affected_method=method_sig,
                        )
                    )

            # If no methods were added this iteration, we're done
            if not methods_added:
                issues = current_issues
                break

        # Extraction is valid only if there are no errors
        has_errors = any(issue.severity == "error" for issue in issues)
        is_valid = not has_errors

        if fixed_issues:
            self.logger.info(
                f"Auto-fixed {len(fixed_issues)} issues for cluster {cluster.id} "
                f"(expanded from {len(cluster_methods) - len(fixed_issues)} to {len(cluster_methods)} methods)"
            )

        if issues:
            self.logger.info(
                f"Validation found {len(issues)} issues for cluster {cluster.id}: "
                f"{sum(1 for i in issues if i.severity == 'error')} errors, "
                f"{sum(1 for i in issues if i.severity == 'warning')} warnings"
            )

        # If static analysis failed but LLM validation is enabled, give LLM a chance to override
        transformation_strategy = None
        if not is_valid and self.llm_validator and self.llm_validator.enabled:
            self.logger.info(
                f"Static validation failed for cluster {cluster.id}, consulting LLM..."
            )

            # Prepare issue descriptions for LLM
            issue_descriptions = [
                f"{issue.issue_type}: {issue.description} (in {issue.affected_method})"
                for issue in issues
                if issue.severity == "error"
            ]

            # Ask LLM if extraction can still work
            llm_result = self.llm_validator.validate_extraction_semantics(
                cluster, class_deps, issue_descriptions
            )

            if llm_result.is_valid and llm_result.confidence >= 0.7:
                self.logger.info(
                    f"LLM overrode static validation for cluster {cluster.id}: "
                    f"confidence={llm_result.confidence:.2f}, reasoning={llm_result.reasoning[:100]}..."
                )
                is_valid = True
                # Add a note to issues
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        issue_type="llm_override",
                        description=f"LLM validated extraction despite static issues (confidence: {llm_result.confidence:.2f})",
                        affected_method="N/A",
                    )
                )
            else:
                self.logger.info(
                    f"LLM confirmed rejection for cluster {cluster.id}: {llm_result.reasoning[:100]}..."
                )

                # LLM confirmed rejection - now suggest pattern transformations
                if self.pattern_transformer and self.pattern_transformer.enabled:
                    self.logger.info(
                        f"Analyzing pattern transformations for cluster {cluster.id}..."
                    )
                    transformation_strategy = self.pattern_transformer.suggest_transformation(
                        cluster, class_deps, issue_descriptions
                    )

                    if transformation_strategy:
                        # Add transformation suggestion to issues
                        issues.append(
                            ValidationIssue(
                                severity="warning",
                                issue_type="pattern_suggestion",
                                description=f"Suggested pattern: {transformation_strategy.pattern_name} (confidence: {transformation_strategy.confidence:.2f})",
                                affected_method="N/A",
                            )
                        )

        # Store transformation strategy in cluster for later retrieval
        if transformation_strategy:
            cluster.transformation_strategy = transformation_strategy

        return is_valid, issues

    def _find_abstract_methods(self, class_deps: ClassDependencies) -> set[str]:
        """Find all abstract methods in the class."""
        abstract = set()
        for method in class_deps.methods:
            if "abstract" in [m.lower() for m in method.modifiers]:
                abstract.add(method.name)
        return abstract

    def _find_abstract_method_calls(
        self,
        method_info: MethodInfo,
        abstract_methods: set[str],
        method_names: dict[str, MethodInfo],
    ) -> set[str]:
        """Find abstract methods called by this method."""
        if not method_info.body:
            return set()

        calls = set()
        # Look for method calls in the body
        for match in re.finditer(r"\b([a-zA-Z_]\w*)\s*\(", method_info.body):
            method_name = match.group(1)
            # Check if this is an abstract method
            if method_name in abstract_methods:
                calls.add(method_name)

        return calls

    def _find_private_method_calls(
        self,
        method_info: MethodInfo,
        class_deps: ClassDependencies,
        cluster_methods: set[str],
        method_by_sig: dict[str, MethodInfo],
    ) -> set[str]:
        """Find private methods called that are not in the cluster."""
        if not method_info.body:
            return set()

        # Get all private methods in the class
        private_methods = {}
        for method in class_deps.methods:
            if "private" in [m.lower() for m in method.modifiers]:
                private_methods[method.name] = method

        calls = set()
        # Look for method calls
        for match in re.finditer(r"\b([a-zA-Z_]\w*)\s*\(", method_info.body):
            method_name = match.group(1)

            # Check if it's a private method
            if method_name in private_methods:
                private_method = private_methods[method_name]
                # Check if it's NOT in the cluster
                if private_method.signature not in cluster_methods:
                    calls.add(method_name)

        return calls

    def _find_inner_class_references(self, method_info: MethodInfo) -> set[str]:
        """Find references to inner classes in method body."""
        if not method_info.body:
            return set()

        refs = set()
        # Look for class instantiations and type references that might be inner classes
        # This is a heuristic - looks for capitalized names that are likely classes
        for match in re.finditer(r"\bnew\s+([A-Z]\w+)\s*\(", method_info.body):
            class_name = match.group(1)
            # Common pattern for inner classes - could be improved
            if class_name not in [
                "String",
                "Integer",
                "Long",
                "Double",
                "Float",
                "Boolean",
                "Character",
                "Byte",
                "Short",
                "StringBuilder",
                "StringBuffer",
                "ArrayList",
                "HashMap",
                "HashSet",
                "LinkedList",
            ]:
                refs.add(class_name)

        # Also look for instance checks and type casts
        for match in re.finditer(r"\binstanceof\s+([A-Z]\w+)", method_info.body):
            refs.add(match.group(1))

        for match in re.finditer(r"\(\s*([A-Z]\w+)\s*\)", method_info.body):
            refs.add(match.group(1))

        return refs
