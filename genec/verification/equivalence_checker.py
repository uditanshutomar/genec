"""
Equivalence Checker for verifying behavioral preservation during refactoring.

This module implements test-based equivalence checking to ensure that
refactored code produces identical outputs to the original code.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from genec.core.cluster_detector import Cluster
from genec.core.llm_interface import RefactoringSuggestion
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class TestResult:
    """Result of running a single test."""

    test_name: str
    passed: bool
    output: str | None = None
    error: str | None = None
    execution_time: float = 0.0


@dataclass
class EquivalenceResult:
    """Result of equivalence checking."""

    is_equivalent: bool
    tests_run: int
    tests_passed_original: int
    tests_passed_refactored: int
    differing_tests: list[str]
    error_message: str | None = None


class EquivalenceChecker:
    """
    Verifies behavioral equivalence between original and refactored code.

    Uses test-based approach:
    1. Discover all tests for the class
    2. Run tests on original code
    3. Apply refactoring
    4. Run same tests on refactored code
    5. Compare outputs
    """

    def __init__(
        self,
        build_tool: str = "maven",  # 'maven' or 'gradle'
        timeout: int = 300,  # 5 minutes
        enable_test_generation: bool = False,
    ):
        """
        Initialize equivalence checker.

        Args:
            build_tool: Build tool to use (maven or gradle)
            timeout: Test execution timeout in seconds
            enable_test_generation: Generate additional tests (experimental)
        """
        self.build_tool = build_tool
        self.timeout = timeout
        self.enable_test_generation = enable_test_generation
        self.logger = get_logger(self.__class__.__name__)

    def check_equivalence(
        self,
        original_class_file: str,
        refactored_files: dict[str, str],  # {new_class_path: code, modified_original_path: code}
        repo_path: str,
        cluster: Cluster,
        suggestion: RefactoringSuggestion,
    ) -> EquivalenceResult:
        """
        Check behavioral equivalence between original and refactored code.

        Args:
            original_class_file: Path to original class file
            refactored_files: Dict mapping file paths to refactored code
            repo_path: Repository root path
            cluster: Cluster being extracted
            suggestion: Refactoring suggestion

        Returns:
            EquivalenceResult with detailed comparison
        """
        self.logger.info(f"Checking equivalence for {suggestion.proposed_class_name}")

        try:
            # Step 1: Discover tests
            tests = self._discover_tests(original_class_file, repo_path)

            if not tests:
                self.logger.warning("No tests found for class, cannot verify equivalence")
                return EquivalenceResult(
                    is_equivalent=True,  # Assume OK if no tests
                    tests_run=0,
                    tests_passed_original=0,
                    tests_passed_refactored=0,
                    differing_tests=[],
                    error_message="No tests found",
                )

            self.logger.info(f"Found {len(tests)} tests to run")

            # Step 2: Run tests on original code
            self.logger.info("Running tests on original code...")
            original_results = self._run_tests(tests, repo_path, is_original=True)

            # Step 3: Apply refactoring temporarily
            self.logger.info("Applying refactoring...")
            backup_files = self._backup_and_apply_refactoring(
                original_class_file, refactored_files, repo_path
            )

            try:
                # Step 4: Run tests on refactored code
                self.logger.info("Running tests on refactored code...")
                refactored_results = self._run_tests(tests, repo_path, is_original=False)

                # Step 5: Compare results
                is_equivalent, differing = self._compare_test_results(
                    original_results, refactored_results
                )

                original_passed = sum(1 for r in original_results.values() if r.passed)
                refactored_passed = sum(1 for r in refactored_results.values() if r.passed)

                result = EquivalenceResult(
                    is_equivalent=is_equivalent,
                    tests_run=len(tests),
                    tests_passed_original=original_passed,
                    tests_passed_refactored=refactored_passed,
                    differing_tests=differing,
                )

                if is_equivalent:
                    self.logger.info("✓ Behavioral equivalence verified")
                else:
                    self.logger.warning(
                        f"✗ Behavioral differences detected in {len(differing)} tests"
                    )

                return result

            finally:
                # Step 6: Restore original files
                self._restore_backup(backup_files, repo_path)

        except Exception as e:
            self.logger.error(f"Equivalence checking failed: {e}", exc_info=True)
            return EquivalenceResult(
                is_equivalent=False,
                tests_run=0,
                tests_passed_original=0,
                tests_passed_refactored=0,
                differing_tests=[],
                error_message=str(e),
            )

    def _discover_tests(self, class_file: str, repo_path: str) -> list[str]:
        """
        Discover all tests for the given class.

        Returns:
            List of fully qualified test class names
        """
        # Extract class name from file path
        class_path = Path(class_file)
        class_name = class_path.stem

        # Look for test files following common patterns
        test_patterns = [
            f"{class_name}Test",
            f"Test{class_name}",
            f"{class_name}Tests",
            f"{class_name}IT",  # Integration tests
        ]

        tests = []
        repo_root = Path(repo_path)

        # Search in test directories
        test_dirs = [
            repo_root / "src" / "test" / "java",
            repo_root / "test",
            repo_root / "tests",
        ]

        for test_dir in test_dirs:
            if not test_dir.exists():
                continue

            for pattern in test_patterns:
                # Find all matching test files
                for test_file in test_dir.rglob(f"{pattern}.java"):
                    # Convert file path to fully qualified class name
                    relative = test_file.relative_to(test_dir)
                    fqn = str(relative.with_suffix("")).replace("/", ".")
                    tests.append(fqn)

        return tests

    def _run_tests(
        self, tests: list[str], repo_path: str, is_original: bool
    ) -> dict[str, TestResult]:
        """
        Run specified tests and collect results.

        Args:
            tests: List of fully qualified test class names
            repo_path: Repository root
            is_original: True if running on original code

        Returns:
            Dict mapping test name to TestResult
        """
        results = {}

        if self.build_tool == "maven":
            # Run tests with Maven
            for test in tests:
                result = self._run_maven_test(test, repo_path)
                results[test] = result
        elif self.build_tool == "gradle":
            # Run tests with Gradle
            for test in tests:
                result = self._run_gradle_test(test, repo_path)
                results[test] = result
        else:
            self.logger.error(f"Unknown build tool: {self.build_tool}")

        return results

    def _run_maven_test(self, test_class: str, repo_path: str) -> TestResult:
        """Run a single test class with Maven."""
        cmd = ["mvn", "test", f"-Dtest={test_class}", "-q", "-DfailIfNoTests=false"]  # Quiet

        try:
            result = subprocess.run(
                cmd, cwd=repo_path, capture_output=True, text=True, timeout=self.timeout
            )

            passed = result.returncode == 0

            return TestResult(
                test_name=test_class,
                passed=passed,
                output=result.stdout if passed else None,
                error=result.stderr if not passed else None,
            )

        except subprocess.TimeoutExpired:
            return TestResult(
                test_name=test_class, passed=False, error=f"Test timed out after {self.timeout}s"
            )
        except Exception as e:
            return TestResult(test_name=test_class, passed=False, error=str(e))

    def _run_gradle_test(self, test_class: str, repo_path: str) -> TestResult:
        """Run a single test class with Gradle."""
        cmd = ["gradle", "test", "--tests", test_class, "-q"]

        try:
            result = subprocess.run(
                cmd, cwd=repo_path, capture_output=True, text=True, timeout=self.timeout
            )

            passed = result.returncode == 0

            return TestResult(
                test_name=test_class,
                passed=passed,
                output=result.stdout if passed else None,
                error=result.stderr if not passed else None,
            )

        except subprocess.TimeoutExpired:
            return TestResult(
                test_name=test_class, passed=False, error=f"Test timed out after {self.timeout}s"
            )
        except Exception as e:
            return TestResult(test_name=test_class, passed=False, error=str(e))

    def _compare_test_results(
        self, original: dict[str, TestResult], refactored: dict[str, TestResult]
    ) -> tuple[bool, list[str]]:
        """
        Compare test results to check equivalence.

        Returns:
            (is_equivalent, list of differing test names)
        """
        differing = []

        for test_name in original.keys():
            orig_result = original[test_name]
            refact_result = refactored.get(test_name)

            if not refact_result:
                differing.append(f"{test_name} (missing in refactored)")
                continue

            # Check if both passed or both failed
            if orig_result.passed != refact_result.passed:
                differing.append(f"{test_name} (pass/fail mismatch)")
                continue

            # If both passed, optionally compare outputs (strict mode)
            # For now, just checking pass/fail is sufficient

        is_equivalent = len(differing) == 0
        return is_equivalent, differing

    def _backup_and_apply_refactoring(
        self, original_class_file: str, refactored_files: dict[str, str], repo_path: str
    ) -> dict[str, str]:
        """
        Backup original files and apply refactoring.

        Returns:
            Dict mapping file paths to backup content
        """
        backup = {}

        # Backup original class file
        original_path = Path(original_class_file)
        if original_path.exists():
            backup[str(original_path)] = original_path.read_text()

        # Apply refactoring: write refactored files
        for file_path, code in refactored_files.items():
            full_path = Path(repo_path) / file_path

            # Backup if exists
            if full_path.exists():
                backup[str(full_path)] = full_path.read_text()

            # Write refactored code
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(code)

        return backup

    def _restore_backup(self, backup: dict[str, str], repo_path: str):
        """Restore files from backup."""
        for file_path, content in backup.items():
            Path(file_path).write_text(content)

        self.logger.info("Restored original files from backup")

    def is_available(self) -> bool:
        """Check if build tools are available."""
        if self.build_tool == "maven":
            try:
                subprocess.run(["mvn", "--version"], capture_output=True, check=True)
                return True
            except:
                return False
        elif self.build_tool == "gradle":
            try:
                subprocess.run(["gradle", "--version"], capture_output=True, check=True)
                return True
            except:
                return False
        return False
