"""
Test discovery strategies for selective testing.

Automatically identifies relevant tests for a refactoring without requiring
predefined project structures.
"""

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


class DiscoveryStrategy(Enum):
    """Test discovery strategies ordered by accuracy."""

    METHOD_CALLS = "method_calls"
    IMPORTS = "imports"
    NAME_MATCHING = "name_matching"
    PACKAGE = "package"
    FULL_SUITE = "full_suite"


@dataclass
class TestSelection:
    """Result of test discovery."""

    tests: list[str]  # Test files or patterns
    test_methods: dict[str, list[str]]  # {test_file: [test_methods]}
    strategy: DiscoveryStrategy
    confidence: float  # 0.0 to 1.0
    estimated_time_seconds: int


class TestDiscoveryEngine:
    """Discovers relevant tests for a refactoring."""

    def __init__(self, repo_path: str, config: dict):
        """
        Initialize test discovery engine.

        Args:
            repo_path: Path to repository root
            config: Configuration dictionary
        """
        self.repo_path = Path(repo_path)
        self.config = config
        self.logger = logger

    def discover_tests(
        self,
        original_class_name: str,
        original_package: str,
        extracted_class_name: str,
        extracted_methods: list[str],
    ) -> TestSelection:
        """
        Discover relevant tests for a refactoring.

        Args:
            original_class_name: Name of original class (e.g., "StringUtils")
            original_package: Package of original class (e.g., "org.apache.commons.lang3")
            extracted_class_name: Name of extracted class (e.g., "StringReplacer")
            extracted_methods: List of method names being extracted

        Returns:
            TestSelection with discovered tests and metadata
        """
        self.logger.info("🔍 Discovering relevant tests...")

        # Try strategies in order of accuracy
        strategies = [
            (self._discover_by_method_calls, DiscoveryStrategy.METHOD_CALLS, 0.95),
            (self._discover_by_imports, DiscoveryStrategy.IMPORTS, 0.85),
            (self._discover_by_name, DiscoveryStrategy.NAME_MATCHING, 0.75),
            (self._discover_by_package, DiscoveryStrategy.PACKAGE, 0.60),
        ]

        for strategy_fn, strategy_type, confidence in strategies:
            result = strategy_fn(
                original_class_name, original_package, extracted_class_name, extracted_methods
            )

            if result and self._is_sufficient(result):
                estimated_time = self._estimate_time(result)
                self.logger.info(
                    f"  Strategy: {strategy_type.value}\n"
                    f"  Discovered: {self._count_tests(result)} tests\n"
                    f"  Confidence: {confidence*100:.0f}%\n"
                    f"  Estimated time: ~{estimated_time}s"
                )

                return TestSelection(
                    tests=result.get("files", []),
                    test_methods=result.get("methods", {}),
                    strategy=strategy_type,
                    confidence=confidence,
                    estimated_time_seconds=estimated_time,
                )

        # Fallback to full suite
        self.logger.warning(
            "  No relevant tests found using selective strategies.\n"
            "  Falling back to full test suite for safety."
        )

        return TestSelection(
            tests=["ALL"],
            test_methods={},
            strategy=DiscoveryStrategy.FULL_SUITE,
            confidence=1.0,
            estimated_time_seconds=self._estimate_full_suite_time(),
        )

    def _discover_by_method_calls(
        self,
        original_class_name: str,
        original_package: str,
        extracted_class_name: str,
        extracted_methods: list[str],
    ) -> dict | None:
        """
        Strategy 1: Find tests that call the extracted methods.

        Most accurate but slowest strategy.
        """
        self.logger.debug("Trying strategy: method call analysis")

        test_files = self._find_test_files()
        if not test_files:
            return None

        matching_tests = {}

        for test_file in test_files:
            try:
                with open(test_file, encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # Find test methods that call extracted methods
                test_methods = self._extract_test_methods(content)

                matching_methods = []
                for test_method_name, test_method_body in test_methods.items():
                    # Check if test method calls any extracted method
                    for extracted_method in extracted_methods:
                        # Pattern: methodName( with optional class prefix
                        pattern = rf"\b{re.escape(extracted_method)}\s*\("

                        if re.search(pattern, test_method_body):
                            matching_methods.append(test_method_name)
                            break

                if matching_methods:
                    matching_tests[str(test_file)] = matching_methods

            except Exception as e:
                self.logger.debug(f"Error parsing {test_file}: {e}")
                continue

        if matching_tests:
            return {"files": list(matching_tests.keys()), "methods": matching_tests}

        return None

    def _discover_by_imports(
        self,
        original_class_name: str,
        original_package: str,
        extracted_class_name: str,
        extracted_methods: list[str],
    ) -> dict | None:
        """
        Strategy 2: Find tests that import the original class.

        Fast and fairly accurate.
        """
        self.logger.debug("Trying strategy: import analysis")

        test_files = self._find_test_files()
        if not test_files:
            return None

        matching_tests = []
        full_class_name = f"{original_package}.{original_class_name}"

        for test_file in test_files:
            try:
                with open(test_file, encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # Check for imports
                if (
                    f"import {full_class_name}" in content
                    or f"import static {full_class_name}" in content
                    or
                    # Also check simple class name usage
                    original_class_name in content
                ):

                    matching_tests.append(str(test_file))

            except Exception as e:
                self.logger.debug(f"Error reading {test_file}: {e}")
                continue

        if matching_tests:
            return {"files": matching_tests, "methods": {}}  # All methods in these files

        return None

    def _discover_by_name(
        self,
        original_class_name: str,
        original_package: str,
        extracted_class_name: str,
        extracted_methods: list[str],
    ) -> dict | None:
        """
        Strategy 3: Find tests by naming conventions.

        Fast and works for most projects.
        """
        self.logger.debug("Trying strategy: name matching")

        # Common test naming patterns
        patterns = [
            f"**/*{original_class_name}Test.java",
            f"**/Test{original_class_name}.java",
            f"**/*{original_class_name}Tests.java",
            f"**/*{original_class_name}TestCase.java",
            # Also check for extracted class tests (may not exist yet)
            f"**/*{extracted_class_name}Test.java",
        ]

        matching_tests = set()

        for pattern in patterns:
            matches = self.repo_path.glob(pattern)
            for match in matches:
                if self._is_test_file(match):
                    matching_tests.add(str(match))

        if matching_tests:
            return {"files": list(matching_tests), "methods": {}}

        return None

    def _discover_by_package(
        self,
        original_class_name: str,
        original_package: str,
        extracted_class_name: str,
        extracted_methods: list[str],
    ) -> dict | None:
        """
        Strategy 4: Find all tests in the same package.

        Fallback for when other strategies find nothing.
        """
        self.logger.debug("Trying strategy: package-level tests")

        # Convert package to path
        package_path = original_package.replace(".", "/")

        # Search for tests in same package
        test_patterns = [
            f"**/test/**/{package_path}/*Test.java",
            f"**/test/**/{package_path}/Test*.java",
        ]

        matching_tests = set()

        for pattern in test_patterns:
            matches = self.repo_path.glob(pattern)
            for match in matches:
                if self._is_test_file(match):
                    matching_tests.add(str(match))

        if matching_tests:
            return {"files": list(matching_tests), "methods": {}}

        return None

    def _find_test_files(self) -> list[Path]:
        """Find all test files in the repository."""
        test_dirs = ["src/test/java", "test", "tests", "src/test", "src/androidTest", "testing"]

        test_files = []

        for test_dir in test_dirs:
            test_path = self.repo_path / test_dir
            if test_path.exists():
                # Find all Java files in test directory
                test_files.extend(test_path.glob("**/*.java"))

        return test_files

    def _is_test_file(self, file_path: Path) -> bool:
        """Check if a file is a test file."""
        name = file_path.name

        # Common test file patterns
        if any(
            [
                name.endswith("Test.java"),
                name.endswith("Tests.java"),
                name.endswith("TestCase.java"),
                name.startswith("Test"),
            ]
        ):
            return True

        # Check content for @Test annotation
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read(5000)  # Read first 5KB
                if "@Test" in content or "@TestTemplate" in content:
                    return True
        except Exception as e:
            self.logger.debug(f"Error checking test file {file_path}: {e}")

        return False

    def _extract_test_methods(self, content: str) -> dict[str, str]:
        """
        Extract test methods and their bodies from Java test file.

        Returns:
            Dict mapping test method name to method body
        """
        test_methods = {}

        # Pattern to match @Test methods
        # Handles multi-line annotations and various formats
        pattern = r"@Test[^{]*?(?:public|protected|private)?\s+(?:static\s+)?void\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+\w+(?:\s*,\s*\w+)*)?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}"

        for match in re.finditer(pattern, content, re.DOTALL):
            method_name = match.group(1)
            method_body = match.group(2)
            test_methods[method_name] = method_body

        return test_methods

    def _is_sufficient(self, result: dict | None) -> bool:
        """Check if discovery result is sufficient to use."""
        if not result:
            return False

        files = result.get("files", [])
        methods = result.get("methods", {})

        # Minimum threshold from config
        min_tests = self.config.get("selective_testing", {}).get("min_tests", 1)

        # Count total test methods
        if methods:
            total_methods = sum(len(m) for m in methods.values())
            return total_methods >= min_tests
        else:
            # If no specific methods, just check files
            return len(files) >= min_tests

    def _count_tests(self, result: dict) -> int:
        """Count number of tests in result."""
        methods = result.get("methods", {})
        if methods:
            return sum(len(m) for m in methods.values())
        else:
            return len(result.get("files", []))

    def _estimate_time(self, result: dict) -> int:
        """Estimate test execution time in seconds."""
        # Rough estimates based on test count
        test_count = self._count_tests(result)

        if test_count == 0:
            test_count = len(result.get("files", [])) * 10  # Assume 10 methods per file

        # Estimate: 2 seconds per test method + 30s overhead
        return 30 + (test_count * 2)

    def _estimate_full_suite_time(self) -> int:
        """Estimate full test suite execution time."""
        # Default estimate: 30 minutes
        # Could be made smarter by analyzing project size
        return 1800
