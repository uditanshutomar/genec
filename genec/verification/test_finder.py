"""
Test finder for incremental verification.

Discovers which test files reference a given class, enabling
targeted test execution rather than running the full suite.
"""

import re
from pathlib import Path

from genec.utils.logging_utils import get_logger


class TestFinder:
    """Finds test files affected by changes to a specific class."""

    def __init__(self, repo_path: Path):
        """
        Initialize test finder.

        Args:
            repo_path: Root path of the repository
        """
        self.repo_path = Path(repo_path)
        self.logger = get_logger(self.__class__.__name__)

        # Common test directory patterns
        self.test_dirs = [
            "src/test/java",
            "test",
            "tests",
            "src/tests",
        ]

        # Common test file patterns
        self.test_patterns = [
            "*Test.java",
            "*Tests.java",
            "Test*.java",
            "*IT.java",  # Integration tests
            "*Spec.java",  # BDD specs
        ]

    def find_affected_tests(self, class_name: str, package_name: str | None = None) -> list[Path]:
        """
        Find test files that reference the given class.

        Args:
            class_name: Name of the class being refactored
            package_name: Optional package name for more precise matching

        Returns:
            List of absolute paths to affected test files
        """
        affected_tests = []

        # Build search patterns
        import_pattern = re.compile(rf"import\s+[\w.]*\.?{re.escape(class_name)}\s*;")
        usage_pattern = re.compile(rf"\b{re.escape(class_name)}\b")

        # Find all test directories
        test_roots = self._find_test_roots()

        if not test_roots:
            self.logger.warning("No test directories found in repository")
            return []

        self.logger.info(
            f"Searching for tests referencing '{class_name}' in {len(test_roots)} test directories"
        )

        # Search test files
        for test_root in test_roots:
            for test_file in self._find_test_files(test_root):
                try:
                    content = test_file.read_text(encoding="utf-8")

                    # Check if test imports or uses the class
                    if import_pattern.search(content) or usage_pattern.search(content):
                        affected_tests.append(test_file)
                        self.logger.debug(f"Found affected test: {test_file.name}")

                except Exception as e:
                    self.logger.debug(f"Error reading {test_file}: {e}")

        self.logger.info(f"Found {len(affected_tests)} tests affected by changes to {class_name}")
        return affected_tests

    def _find_test_roots(self) -> list[Path]:
        """Find test root directories in the repository."""
        roots = []

        for test_dir in self.test_dirs:
            test_path = self.repo_path / test_dir
            if test_path.exists() and test_path.is_dir():
                roots.append(test_path)

        return roots

    def _find_test_files(self, test_root: Path) -> list[Path]:
        """Find all test files in a test directory."""
        test_files = []

        for pattern in self.test_patterns:
            test_files.extend(test_root.rglob(pattern))

        return list(set(test_files))  # Remove duplicates

    def get_test_class_names(self, test_files: list[Path]) -> list[str]:
        """
        Extract test class names from file paths.

        Useful for running specific tests with Maven/Gradle.

        Args:
            test_files: List of test file paths

        Returns:
            List of fully qualified test class names
        """
        class_names = []

        for test_file in test_files:
            try:
                # Read file to extract package
                content = test_file.read_text(encoding="utf-8")

                # Extract package name
                package_match = re.search(r"package\s+([\w.]+)\s*;", content)
                package = package_match.group(1) if package_match else ""

                # Get class name from file name
                class_name = test_file.stem

                if package:
                    class_names.append(f"{package}.{class_name}")
                else:
                    class_names.append(class_name)

            except Exception as e:
                self.logger.debug(f"Error extracting class name from {test_file}: {e}")

        return class_names

    def build_maven_test_command(self, test_classes: list[str]) -> list[str]:
        """
        Build Maven command to run specific tests.

        Args:
            test_classes: List of fully qualified test class names

        Returns:
            Maven command as list of arguments
        """
        if not test_classes:
            return ["mvn", "test"]

        # Maven Surefire plugin syntax for running specific tests
        test_pattern = ",".join(test_classes)
        return ["mvn", "test", f"-Dtest={test_pattern}", "-DfailIfNoTests=false"]

    def build_gradle_test_command(self, test_classes: list[str]) -> list[str]:
        """
        Build Gradle command to run specific tests.

        Args:
            test_classes: List of fully qualified test class names

        Returns:
            Gradle command as list of arguments
        """
        if not test_classes:
            return ["gradle", "test"]

        # Gradle test filter syntax
        filters = " ".join([f"--tests {tc}" for tc in test_classes])
        return ["gradle", "test"] + [f"--tests {tc}" for tc in test_classes]
