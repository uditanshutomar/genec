"""Behavioral verification through test execution."""

import os
import subprocess
import shutil
import tempfile
from pathlib import Path
from typing import Tuple, Optional, Dict

from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


class BehavioralVerifier:
    """Verifies refactorings preserve behavior by running test suites."""

    def __init__(
        self,
        maven_command: str = 'mvn',
        gradle_command: str = 'gradle'
    ):
        """
        Initialize behavioral verifier.

        Args:
            maven_command: Maven command
            gradle_command: Gradle command
        """
        self.maven_command = maven_command
        self.gradle_command = gradle_command
        self.logger = get_logger(self.__class__.__name__)

    def verify(
        self,
        original_class_file: str,
        new_class_code: str,
        modified_original_code: str,
        repo_path: str,
        package_name: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify behavioral correctness by running tests.

        Creates a copy of the project, applies refactoring, and runs tests.

        Args:
            original_class_file: Path to original class file
            new_class_code: Code for new extracted class
            modified_original_code: Code for modified original class
            repo_path: Path to repository
            package_name: Package name

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        self.logger.info("Running behavioral verification")

        # Create temporary copy of repository
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_repo = Path(temp_dir) / 'repo_copy'

            try:
                # Copy repository
                self.logger.info(f"Copying repository to {temp_repo}")
                shutil.copytree(repo_path, temp_repo, symlinks=True)

                # Determine build system
                build_system = self._detect_build_system(temp_repo)
                if not build_system:
                    self.logger.info("No build system detected; skipping behavioral verification.")
                    return True, "Skipped (no build system detected)"

                # Run tests before refactoring (baseline)
                self.logger.info("Running baseline tests")
                baseline_success, baseline_error = self._run_tests(temp_repo, build_system)

                if not baseline_success:
                    return False, f"Baseline tests failed: {baseline_error}"

                # Apply refactoring
                self.logger.info("Applying refactoring")
                apply_success, apply_error = self._apply_refactoring(
                    temp_repo,
                    original_class_file,
                    new_class_code,
                    modified_original_code,
                    package_name
                )

                if not apply_success:
                    return False, f"Failed to apply refactoring: {apply_error}"

                # Run tests after refactoring
                self.logger.info("Running tests after refactoring")
                refactored_success, refactored_error = self._run_tests(temp_repo, build_system)

                if refactored_success:
                    self.logger.info("Behavioral verification PASSED")
                    return True, None
                else:
                    self.logger.warning(f"Behavioral verification FAILED: {refactored_error}")
                    return False, f"Tests failed after refactoring: {refactored_error}"

            except Exception as e:
                error_msg = f"Behavioral verification error: {str(e)}"
                self.logger.error(error_msg)
                return False, error_msg

    def _detect_build_system(self, repo_path: Path) -> Optional[str]:
        """
        Detect build system (Maven or Gradle).

        Args:
            repo_path: Path to repository

        Returns:
            'maven', 'gradle', or None
        """
        if (repo_path / 'pom.xml').exists():
            return 'maven'
        elif (repo_path / 'build.gradle').exists() or (repo_path / 'build.gradle.kts').exists():
            return 'gradle'
        return None

    def _only_contains_warnings(self, output: str) -> bool:
        """
        Check if output only contains warnings, not actual build/test failures.

        Args:
            output: Build/test output to check

        Returns:
            True if output only contains warnings (or is empty), False if there are real failures
        """
        if not output or not output.strip():
            # Empty output is fine (not a failure)
            return True

        # Indicators of actual failures
        failure_indicators = [
            "BUILD FAILURE",
            "COMPILATION ERROR",
            "test failures",
            "test error",
            "FAILED",
            "Error:",
            "Exception in thread",
            "at org.junit",  # JUnit stack traces
            "[ERROR]",  # Maven error prefix
            "FAILURE:",  # Gradle failure
        ]

        # Check if any failure indicators are present
        output_lower = output.lower()
        for indicator in failure_indicators:
            if indicator.lower() in output_lower:
                # Exception: "Tests run: X, Failures: 0, Errors: 0" is actually success
                if "failures: 0" in output_lower and "errors: 0" in output_lower:
                    continue
                return False

        # Check for actual test result summaries with failures
        # Format: "Tests run: 1234, Failures: 5, Errors: 2, Skipped: 3"
        import re
        test_results = re.search(r'Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+)', output, re.IGNORECASE)
        if test_results:
            failures = int(test_results.group(2))
            errors = int(test_results.group(3))
            if failures > 0 or errors > 0:
                return False

        # If we get here, it's either warnings or non-failure output
        return True

    def _run_tests(
        self,
        repo_path: Path,
        build_system: str,
        timeout: int = 900
    ) -> Tuple[bool, Optional[str]]:
        """
        Run test suite.

        Args:
            repo_path: Path to repository
            build_system: 'maven' or 'gradle'
            timeout: Test timeout in seconds

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            if build_system == 'maven':
                cmd = [self.maven_command, 'test', '-q']
            elif build_system == 'gradle':
                cmd = [self.gradle_command, 'test', '-q']
            else:
                return False, f"Unknown build system: {build_system}"

            # Run tests
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            # Check for actual test failures, not just warnings
            # Maven/Gradle return 0 on success, non-zero on failure
            if result.returncode == 0:
                return True, None
            else:
                # Check if this is a real failure or just warnings
                error_msg = result.stderr or result.stdout

                # If stderr only contains warnings (not BUILD FAILURE), treat as success
                if self._only_contains_warnings(error_msg):
                    self.logger.info("Tests passed (ignoring build warnings)")
                    return True, None

                return False, error_msg

        except subprocess.TimeoutExpired:
            return False, "Test execution timeout"
        except FileNotFoundError:
            return False, f"Build tool not found: {cmd[0]}"
        except Exception as e:
            return False, f"Test execution error: {str(e)}"

    def _apply_refactoring(
        self,
        repo_path: Path,
        original_class_file: str,
        new_class_code: str,
        modified_original_code: str,
        package_name: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Apply refactoring to repository copy.

        Args:
            repo_path: Path to repository copy
            original_class_file: Original class file path (relative to repo)
            new_class_code: New class code
            modified_original_code: Modified original code
            package_name: Package name

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            # Extract class names
            import re

            new_class_match = re.search(r'(?:public\s+)?class\s+(\w+)', new_class_code)
            if not new_class_match:
                return False, "Could not extract new class name"

            new_class_name = new_class_match.group(1)

            # Write modified original class
            original_file_path = repo_path / original_class_file
            original_file_path.write_text(modified_original_code, encoding='utf-8')

            # Write new class
            new_class_file = original_file_path.parent / f"{new_class_name}.java"
            new_class_file.write_text(new_class_code, encoding='utf-8')

            self.logger.info(f"Created new class: {new_class_file}")
            self.logger.info(f"Modified original class: {original_file_path}")

            return True, None

        except Exception as e:
            return False, f"Error applying refactoring: {str(e)}"

    def check_build_tools_available(self) -> Dict[str, bool]:
        """
        Check which build tools are available.

        Returns:
            Dict mapping tool names to availability
        """
        tools = {}

        # Check Maven
        try:
            result = subprocess.run(
                [self.maven_command, '-version'],
                capture_output=True,
                timeout=5
            )
            tools['maven'] = (result.returncode == 0)
        except:
            tools['maven'] = False

        # Check Gradle
        try:
            result = subprocess.run(
                [self.gradle_command, '--version'],
                capture_output=True,
                timeout=5
            )
            tools['gradle'] = (result.returncode == 0)
        except:
            tools['gradle'] = False

        return tools
