"""
Hybrid dependency analyzer using Spoon (primary) and JavaParser (fallback).

This analyzer provides the best of both worlds:
- Spoon: Production-grade accuracy, full Java language support
- JavaParser: Lightweight fallback when Spoon is unavailable or fails

Architecture:
    1. Try Spoon first (most reliable)
    2. Fall back to JavaParser if Spoon fails
    3. Track success/failure metrics for monitoring
"""

from dataclasses import dataclass

import numpy as np

from genec.core.dependency_analyzer import (
    ClassDependencies,
    DependencyAnalyzer,
    FieldInfo,
    MethodInfo,
)
from genec.parsers.spoon_parser import SpoonParser, SpoonParserError
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class AnalysisMetrics:
    """Track which parser was used for analysis."""

    total_analyses: int = 0
    spoon_successes: int = 0
    spoon_failures: int = 0
    fallback_successes: int = 0
    fallback_failures: int = 0

    def get_spoon_success_rate(self) -> float:
        """Get Spoon success rate as percentage."""
        if self.total_analyses == 0:
            return 0.0
        return (self.spoon_successes / self.total_analyses) * 100

    def get_fallback_usage_rate(self) -> float:
        """Get fallback usage rate as percentage."""
        if self.total_analyses == 0:
            return 0.0
        return ((self.fallback_successes + self.fallback_failures) / self.total_analyses) * 100

    def get_summary(self) -> str:
        """Get human-readable summary."""
        return (
            f"Total: {self.total_analyses}, "
            f"Spoon: {self.spoon_successes}/{self.spoon_successes + self.spoon_failures} "
            f"({self.get_spoon_success_rate():.1f}%), "
            f"Fallback: {self.fallback_successes}/{self.fallback_successes + self.fallback_failures}"
        )


class HybridDependencyAnalyzer:
    """
    Hybrid dependency analyzer with Spoon primary and JavaParser fallback.

    This analyzer attempts to use Spoon first for the most accurate analysis,
    but gracefully falls back to our JavaParser implementation if Spoon
    is unavailable or fails.

    Usage:
        analyzer = HybridDependencyAnalyzer()
        result = analyzer.analyze_class("MyClass.java")

        # Check which parser was used
        print(analyzer.metrics.get_summary())
    """

    # Dependency weights (same as DependencyAnalyzer)
    WEIGHT_METHOD_CALL = 1.0
    WEIGHT_FIELD_ACCESS = 0.8
    WEIGHT_SHARED_FIELD = 0.6

    def __init__(self, spoon_wrapper_jar: str | None = None, prefer_spoon: bool = True):
        """
        Initialize hybrid dependency analyzer.

        Args:
            spoon_wrapper_jar: Path to Spoon wrapper JAR (None = auto-detect)
            prefer_spoon: If True, use Spoon when available (default: True)
        """
        self.logger = get_logger(self.__class__.__name__)
        self.prefer_spoon = prefer_spoon
        self.metrics = AnalysisMetrics()

        # Initialize Spoon parser (may fail if JAR not available)
        self.spoon_parser = None
        if prefer_spoon:
            try:
                self.spoon_parser = SpoonParser(spoon_wrapper_jar)
                if self.spoon_parser.is_available():
                    self.logger.info("Spoon parser initialized successfully")
                else:
                    self.logger.warning("Spoon parser not available, using fallback only")
                    self.spoon_parser = None
            except Exception as e:
                self.logger.warning(f"Failed to initialize Spoon parser: {e}")
                self.spoon_parser = None

        # Initialize fallback parser (always available)
        self.fallback_analyzer = DependencyAnalyzer()
        self.logger.info(
            f"Hybrid analyzer initialized: "
            f"Spoon={'available' if self.spoon_parser else 'unavailable'}, "
            f"Fallback=available"
        )

    def analyze_class(self, class_file: str) -> ClassDependencies | None:
        """
        Analyze a Java class file with hybrid approach.

        Tries Spoon first, falls back to JavaParser if Spoon fails.

        Args:
            class_file: Path to Java source file

        Returns:
            ClassDependencies object or None if all parsers fail
        """
        self.metrics.total_analyses += 1
        self.logger.info(f"Analyzing class (hybrid): {class_file}")

        # Try Spoon first if available and preferred
        if self.spoon_parser and self.prefer_spoon:
            try:
                result = self._analyze_with_spoon(class_file)
                if result:
                    self.metrics.spoon_successes += 1
                    self.logger.info(f"✓ Spoon analysis successful: {class_file}")
                    return result
            except SpoonParserError as e:
                self.metrics.spoon_failures += 1
                self.logger.warning(f"Spoon analysis failed, falling back to JavaParser: {e}")
            except Exception as e:
                self.metrics.spoon_failures += 1
                self.logger.warning(f"Unexpected Spoon error, falling back to JavaParser: {e}")

        # Fall back to JavaParser
        self.logger.info(f"Using fallback JavaParser for: {class_file}")
        try:
            result = self.fallback_analyzer.analyze_class(class_file)
            if result:
                self.metrics.fallback_successes += 1
                self.logger.info(f"✓ Fallback analysis successful: {class_file}")
                return result
            else:
                self.metrics.fallback_failures += 1
                self.logger.error(f"✗ Fallback analysis failed: {class_file}")
                return None
        except Exception as e:
            self.metrics.fallback_failures += 1
            self.logger.error(f"✗ Fallback analysis error: {e}")
            return None

    def _analyze_with_spoon(self, class_file: str) -> ClassDependencies | None:
        """
        Analyze class using Spoon parser.

        Args:
            class_file: Path to Java source file

        Returns:
            ClassDependencies object or None if analysis fails

        Raises:
            SpoonParserError: If Spoon analysis fails
        """
        # Get analysis from Spoon
        spoon_result = self.spoon_parser.analyze_class(class_file)
        if not spoon_result:
            raise SpoonParserError("Spoon returned no result")

        # Convert Spoon result to ClassDependencies format
        methods = []
        for spoon_method in spoon_result.methods:
            method_info = MethodInfo(
                name=spoon_method["name"],
                signature=spoon_method["signature"],
                return_type=spoon_method.get("returnType", ""),
                modifiers=spoon_method.get("modifiers", []),
                parameters=spoon_method.get("parameters", []),
                start_line=spoon_method.get("startLine", 0),
                end_line=spoon_method.get("endLine", 0),
                body=spoon_method.get("body", ""),
            )
            methods.append(method_info)

        constructors = []
        for spoon_ctor in spoon_result.constructors:
            ctor_info = MethodInfo(
                name=spoon_ctor["name"],
                signature=spoon_ctor["signature"],
                return_type="",
                modifiers=spoon_ctor.get("modifiers", []),
                parameters=spoon_ctor.get("parameters", []),
                start_line=spoon_ctor.get("startLine", 0),
                end_line=spoon_ctor.get("endLine", 0),
                body=spoon_ctor.get("body", ""),
            )
            constructors.append(ctor_info)

        fields = []
        for spoon_field in spoon_result.fields:
            field_info = FieldInfo(
                name=spoon_field["name"],
                type=spoon_field.get("type", ""),
                modifiers=spoon_field.get("modifiers", []),
                line_number=spoon_field.get("lineNumber", 0),
            )
            fields.append(field_info)

        # Create ClassDependencies object
        class_deps = ClassDependencies(
            class_name=spoon_result.class_name,
            package_name=spoon_result.package_name,
            file_path=class_file,
            methods=methods,
            fields=fields,
            constructors=constructors,
            method_calls=spoon_result.method_calls,
            field_accesses=spoon_result.field_accesses,
        )

        # Build dependency matrix
        self._build_dependency_matrix(class_deps)

        self.logger.info(
            f"Spoon analyzed {class_deps.class_name}: "
            f"{len(methods)} methods, {len(constructors)} constructors, "
            f"{len(fields)} fields"
        )

        return class_deps

    def _build_dependency_matrix(self, class_deps: ClassDependencies):
        """
        Build dependency matrix for all members (same logic as DependencyAnalyzer).

        Args:
            class_deps: ClassDependencies object to populate
        """
        all_methods = class_deps.get_all_methods()

        # Create member name list (methods first, then fields)
        member_names = [m.signature for m in all_methods] + [f.name for f in class_deps.fields]
        class_deps.member_names = member_names

        n = len(member_names)
        matrix = np.zeros((n, n))

        # Create index maps
        method_to_idx = {m.signature: i for i, m in enumerate(all_methods)}
        field_to_idx = {f.name: i + len(all_methods) for i, f in enumerate(class_deps.fields)}

        # Build name-to-signature mapping for overload resolution
        name_to_methods = {}
        for m in all_methods:
            if m.name not in name_to_methods:
                name_to_methods[m.name] = []
            name_to_methods[m.name].append(m)

        # Fill matrix with dependencies
        for method in all_methods:
            method_idx = method_to_idx[method.signature]

            # Method calls
            for called_method_name in class_deps.method_calls.get(method.signature, []):
                # Find all overloads of the called method
                overloaded_methods = name_to_methods.get(called_method_name, [])

                if len(overloaded_methods) == 1:
                    # No overloading, direct match
                    called_idx = method_to_idx[overloaded_methods[0].signature]
                    matrix[method_idx][called_idx] = self.WEIGHT_METHOD_CALL
                else:
                    # Multiple overloads exist
                    weight = self.WEIGHT_METHOD_CALL * 0.9
                    for overloaded_method in overloaded_methods:
                        called_idx = method_to_idx[overloaded_method.signature]
                        matrix[method_idx][called_idx] = max(matrix[method_idx][called_idx], weight)

            # Field accesses
            for field_name in class_deps.field_accesses.get(method.signature, []):
                if field_name in field_to_idx:
                    field_idx = field_to_idx[field_name]
                    matrix[method_idx][field_idx] = self.WEIGHT_FIELD_ACCESS

        # Add shared field dependencies
        for field_name, field_idx in field_to_idx.items():
            accessing_methods = []
            for method in all_methods:
                if field_name in class_deps.field_accesses.get(method.signature, []):
                    accessing_methods.append(method_to_idx[method.signature])

            for i in range(len(accessing_methods)):
                for j in range(i + 1, len(accessing_methods)):
                    idx1, idx2 = accessing_methods[i], accessing_methods[j]
                    matrix[idx1][idx2] = max(matrix[idx1][idx2], self.WEIGHT_SHARED_FIELD)
                    matrix[idx2][idx1] = max(matrix[idx2][idx1], self.WEIGHT_SHARED_FIELD)

        class_deps.dependency_matrix = matrix

    def get_metrics_summary(self) -> str:
        """Get human-readable metrics summary."""
        return self.metrics.get_summary()

    def print_metrics(self):
        """Print analysis metrics to console."""
        print("=" * 80)
        print("HYBRID DEPENDENCY ANALYZER METRICS")
        print("=" * 80)
        print(self.metrics.get_summary())
        print()
        if self.metrics.total_analyses > 0:
            spoon_rate = self.metrics.get_spoon_success_rate()
            fallback_rate = (self.metrics.fallback_successes / self.metrics.total_analyses) * 100
            print(f"Spoon Success Rate: {spoon_rate:.1f}%")
            print(f"Fallback Usage Rate: {fallback_rate:.1f}%")
            if self.metrics.fallback_failures > 0:
                print(f"⚠️  Total Failures: {self.metrics.fallback_failures}")
        print("=" * 80)
