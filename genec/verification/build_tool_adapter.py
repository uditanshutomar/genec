"""
Build tool adapters for running selective tests.

Supports Maven, Gradle, and other build systems.
"""

import subprocess
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path

from genec.utils.logging_utils import get_logger
from genec.verification.test_discovery import DiscoveryStrategy, TestSelection

logger = get_logger(__name__)


class BuildTool(Enum):
    """Supported build tools."""

    MAVEN = "maven"
    GRADLE = "gradle"
    ANT = "ant"
    UNKNOWN = "unknown"


class BuildToolAdapter(ABC):
    """Base class for build tool adapters."""

    def __init__(self, repo_path: str):
        """
        Initialize build tool adapter.

        Args:
            repo_path: Path to repository root
        """
        self.repo_path = Path(repo_path)
        self.logger = logger

    @abstractmethod
    def run_tests(
        self, test_selection: TestSelection, timeout_seconds: int = 1800
    ) -> subprocess.CompletedProcess:
        """
        Run tests using this build tool.

        Args:
            test_selection: Test selection from discovery
            timeout_seconds: Timeout for test execution

        Returns:
            CompletedProcess result
        """
        pass

    @abstractmethod
    def run_all_tests(self, timeout_seconds: int = 1800) -> subprocess.CompletedProcess:
        """Run all tests in the project."""
        pass


class MavenAdapter(BuildToolAdapter):
    """Adapter for Maven projects."""

    def run_tests(
        self, test_selection: TestSelection, timeout_seconds: int = 1800
    ) -> subprocess.CompletedProcess:
        """Run selective tests with Maven."""
        if test_selection.strategy == DiscoveryStrategy.FULL_SUITE:
            return self.run_all_tests(timeout_seconds)

        # Build test pattern for Maven
        test_pattern = self._build_test_pattern(test_selection)

        command = [
            "mvn",
            "test",
            "-q",  # Quiet mode
            "-DskipTests=false",
            "-Drat.skip=true",  # Skip Apache RAT license checks during verification
        ]

        if test_pattern:
            command.append(f"-Dtest={test_pattern}")

        self.logger.info(f"Running Maven tests: {' '.join(command)}")

        try:
            result = subprocess.run(
                command, cwd=self.repo_path, capture_output=True, text=True, timeout=timeout_seconds
            )
            return result
        except subprocess.TimeoutExpired:
            self.logger.error(f"Maven tests timed out after {timeout_seconds}s")
            raise

    def run_all_tests(self, timeout_seconds: int = 1800) -> subprocess.CompletedProcess:
        """Run all Maven tests."""
        command = ["mvn", "test", "-q", "-Drat.skip=true"]  # Skip Apache RAT license checks

        self.logger.info("Running all Maven tests")

        try:
            result = subprocess.run(
                command, cwd=self.repo_path, capture_output=True, text=True, timeout=timeout_seconds
            )
            return result
        except subprocess.TimeoutExpired:
            self.logger.error(f"Maven tests timed out after {timeout_seconds}s")
            raise

    def _build_test_pattern(self, test_selection: TestSelection) -> str:
        """
        Build Maven test pattern.

        Maven supports:
        - TestClass1,TestClass2 (multiple classes)
        - TestClass#testMethod1+testMethod2 (specific methods)
        """
        if test_selection.test_methods:
            # Specific methods specified
            patterns = []

            for test_file, methods in test_selection.test_methods.items():
                # Extract class name from file path
                class_name = self._extract_class_name(test_file)

                if methods:
                    # Specific methods: ClassName#method1+method2
                    method_list = "+".join(methods)
                    patterns.append(f"{class_name}#{method_list}")
                else:
                    # Entire class
                    patterns.append(class_name)

            return ",".join(patterns)
        else:
            # Just file patterns - extract class names
            class_names = [self._extract_class_name(f) for f in test_selection.tests if f != "ALL"]
            return ",".join(class_names) if class_names else "*Test"

    def _extract_class_name(self, file_path: str) -> str:
        """Extract Java class name from file path."""
        path = Path(file_path)
        # Remove .java extension and get name
        class_name = path.stem

        # If path contains package structure, use qualified name
        # Example: src/test/java/com/example/FooTest.java -> com.example.FooTest
        parts = path.parts

        try:
            # Find 'java' directory
            java_idx = parts.index("java")
            # Package is everything after 'java' directory
            package_parts = parts[java_idx + 1 : -1]
            if package_parts:
                package = ".".join(package_parts)
                return f"{package}.{class_name}"
        except (ValueError, IndexError):
            pass

        return class_name


class GradleAdapter(BuildToolAdapter):
    """Adapter for Gradle projects."""

    def run_tests(
        self, test_selection: TestSelection, timeout_seconds: int = 1800
    ) -> subprocess.CompletedProcess:
        """Run selective tests with Gradle."""
        if test_selection.strategy == DiscoveryStrategy.FULL_SUITE:
            return self.run_all_tests(timeout_seconds)

        # Build test pattern for Gradle
        test_patterns = self._build_test_patterns(test_selection)

        command = ["./gradlew", "test", "-q"]

        for pattern in test_patterns:
            command.append("--tests")
            command.append(pattern)

        self.logger.info(f"Running Gradle tests: {' '.join(command)}")

        try:
            result = subprocess.run(
                command, cwd=self.repo_path, capture_output=True, text=True, timeout=timeout_seconds
            )
            return result
        except subprocess.TimeoutExpired:
            self.logger.error(f"Gradle tests timed out after {timeout_seconds}s")
            raise

    def run_all_tests(self, timeout_seconds: int = 1800) -> subprocess.CompletedProcess:
        """Run all Gradle tests."""
        command = ["./gradlew", "test", "-q"]

        self.logger.info("Running all Gradle tests")

        try:
            result = subprocess.run(
                command, cwd=self.repo_path, capture_output=True, text=True, timeout=timeout_seconds
            )
            return result
        except subprocess.TimeoutExpired:
            self.logger.error(f"Gradle tests timed out after {timeout_seconds}s")
            raise

    def _build_test_patterns(self, test_selection: TestSelection) -> list[str]:
        """
        Build Gradle test patterns.

        Gradle supports:
        - --tests ClassName
        - --tests ClassName.methodName
        - --tests *.PartialName*
        """
        patterns = []

        if test_selection.test_methods:
            for test_file, methods in test_selection.test_methods.items():
                class_name = self._extract_class_name(test_file)

                if methods:
                    # Add each method
                    for method in methods:
                        patterns.append(f"{class_name}.{method}")
                else:
                    patterns.append(class_name)
        else:
            # Just files
            for test_file in test_selection.tests:
                if test_file != "ALL":
                    class_name = self._extract_class_name(test_file)
                    patterns.append(class_name)

        return patterns if patterns else ["*Test"]

    def _extract_class_name(self, file_path: str) -> str:
        """Extract fully qualified class name from file path."""
        # Similar to Maven adapter
        path = Path(file_path)
        class_name = path.stem

        parts = path.parts
        try:
            java_idx = parts.index("java")
            package_parts = parts[java_idx + 1 : -1]
            if package_parts:
                package = ".".join(package_parts)
                return f"{package}.{class_name}"
        except (ValueError, IndexError):
            pass

        return class_name


class AntAdapter(BuildToolAdapter):
    """Adapter for Ant projects."""

    def run_tests(
        self, test_selection: TestSelection, timeout_seconds: int = 1800
    ) -> subprocess.CompletedProcess:
        """Run tests with Ant."""
        # Ant doesn't have good selective test support
        # Fall back to running all tests
        self.logger.warning("Ant doesn't support selective testing well. Running all tests.")
        return self.run_all_tests(timeout_seconds)

    def run_all_tests(self, timeout_seconds: int = 1800) -> subprocess.CompletedProcess:
        """Run all Ant tests."""
        command = ["ant", "test"]

        self.logger.info("Running all Ant tests")

        try:
            result = subprocess.run(
                command, cwd=self.repo_path, capture_output=True, text=True, timeout=timeout_seconds
            )
            return result
        except subprocess.TimeoutExpired:
            self.logger.error(f"Ant tests timed out after {timeout_seconds}s")
            raise


def detect_build_tool(repo_path: str) -> BuildTool:
    """
    Detect which build tool a project uses.

    Args:
        repo_path: Path to repository root

    Returns:
        Detected build tool
    """
    repo = Path(repo_path)

    # Check for Maven
    if (repo / "pom.xml").exists():
        return BuildTool.MAVEN

    # Check for Gradle
    if (repo / "build.gradle").exists() or (repo / "build.gradle.kts").exists():
        return BuildTool.GRADLE

    # Check for Ant
    if (repo / "build.xml").exists():
        return BuildTool.ANT

    return BuildTool.UNKNOWN


def create_build_adapter(
    repo_path: str, build_tool: BuildTool | None = None
) -> BuildToolAdapter:
    """
    Create appropriate build tool adapter.

    Args:
        repo_path: Path to repository root
        build_tool: Build tool to use (auto-detected if None)

    Returns:
        Build tool adapter instance
    """
    if build_tool is None:
        build_tool = detect_build_tool(repo_path)

    if build_tool == BuildTool.MAVEN:
        return MavenAdapter(repo_path)
    elif build_tool == BuildTool.GRADLE:
        return GradleAdapter(repo_path)
    elif build_tool == BuildTool.ANT:
        return AntAdapter(repo_path)
    else:
        # Default to Maven as fallback
        logger.warning("Unknown build tool, defaulting to Maven")
        return MavenAdapter(repo_path)
