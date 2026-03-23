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

from genec.core.dependency_analyzer import (
    ClassDependencies,
    DependencyAnalyzer,
    FieldInfo,
    MethodInfo,
    build_dependency_matrix,
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
        self.logger.info(analyzer.metrics.get_summary())
    """

    def __init__(self, spoon_wrapper_jar: str | None = None, prefer_spoon: bool = True, use_spoon: bool = False):
        """
        Initialize hybrid dependency analyzer.

        Args:
            spoon_wrapper_jar: Path to Spoon wrapper JAR (None = auto-detect)
            prefer_spoon: If True, use Spoon when available (default: True)
            use_spoon: If False (default), skip Spoon entirely (no warnings).
                       Only try Spoon when explicitly set to True via config.
        """
        self.logger = get_logger(self.__class__.__name__)
        self.prefer_spoon = prefer_spoon and use_spoon
        self.metrics = AnalysisMetrics()

        # Initialize Spoon parser only if explicitly enabled via config
        self.spoon_parser = None
        if self.prefer_spoon:
            try:
                self.spoon_parser = SpoonParser(spoon_wrapper_jar)
                if self.spoon_parser.is_available():
                    self.logger.info("Spoon parser initialized successfully")
                else:
                    self.logger.info("Spoon parser not available, using javalang only")
                    self.spoon_parser = None
            except Exception as e:
                self.logger.info(f"Spoon parser unavailable: {e}")
                self.spoon_parser = None

        # Initialize fallback parser (always available)
        self.fallback_analyzer = DependencyAnalyzer()
        if not use_spoon:
            self.logger.debug("Spoon disabled (use_spoon=false), using javalang only")
        else:
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
        """Build dependency matrix — delegates to shared module-level function."""
        build_dependency_matrix(class_deps)

    def get_metrics_summary(self) -> str:
        """Get human-readable metrics summary."""
        return self.metrics.get_summary()

    def print_metrics(self):
        """Log analysis metrics."""
        self.logger.info("=" * 80)
        self.logger.info("HYBRID DEPENDENCY ANALYZER METRICS")
        self.logger.info("=" * 80)
        self.logger.info(self.metrics.get_summary())
        if self.metrics.total_analyses > 0:
            spoon_rate = self.metrics.get_spoon_success_rate()
            fallback_rate = (self.metrics.fallback_successes / self.metrics.total_analyses) * 100
            self.logger.info(f"Spoon Success Rate: {spoon_rate:.1f}%")
            self.logger.info(f"Fallback Usage Rate: {fallback_rate:.1f}%")
            if self.metrics.fallback_failures > 0:
                self.logger.info(f"Total Failures: {self.metrics.fallback_failures}")
        self.logger.info("=" * 80)
