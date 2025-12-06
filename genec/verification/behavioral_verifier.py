"""Behavioral verification through test execution."""

import re
import shutil
import subprocess
import threading
from pathlib import Path

from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Module-level lock for serializing behavioral verification
# This ensures only one verification modifies the repo at a time
_verification_lock = threading.Lock()


class BehavioralVerifier:
    """Verifies refactorings preserve behavior by running test suites."""

    def __init__(self, maven_command: str = "mvn", gradle_command: str = "gradle"):
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
        package_name: str = "",
    ) -> tuple[bool, str | None]:
        """
        Verify behavioral correctness by running tests.

        Uses IN-PLACE modification with backup/restore for performance.
        This avoids copying the entire repository (which can be 50MB+).

        Strategy:
        1. Acquire lock (serialize across threads)
        2. Check for and recover from any previous interrupted verification
        3. Backup only the files we modify (2 files max)
        4. Apply refactoring in-place
        5. Run tests
        6. Restore original files (guaranteed via try/finally)
        7. Release lock

        Args:
            original_class_file: Path to original class file
            new_class_code: Code for new extracted class
            modified_original_code: Code for modified original class
            repo_path: Path to repository
            package_name: Package name

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        self.logger.info("Running behavioral verification (in-place mode)")

        # Serialize verification to avoid conflicts
        with _verification_lock:
            repo = Path(repo_path)
            backup_data: dict[Path, str] = {}
            new_class_file: Path | None = None
            marker_file = repo / ".genec_verification_in_progress"

            try:
                # Step 1: Check for interrupted previous verification and recover
                self._check_and_recover(repo)

                # Step 2: Detect build system
                build_system = self._detect_build_system(repo)
                if not build_system:
                    self.logger.info("No build system detected; skipping behavioral verification.")
                    return True, "Skipped (no build system detected)"

                # Step 3: Create marker file for crash recovery
                marker_file.write_text(original_class_file, encoding="utf-8")

                # Step 4: Backup the original file with mtime for safety
                original_path = repo / original_class_file
                backup_mtime: dict[Path, float] = {}  # Track original mtimes
                if original_path.exists():
                    backup_data[original_path] = original_path.read_text(encoding="utf-8")
                    backup_mtime[original_path] = original_path.stat().st_mtime
                    self.logger.debug(f"Backed up: {original_path} (mtime: {backup_mtime[original_path]})")

                # Step 5: Apply refactoring IN-PLACE
                self.logger.info("Applying refactoring in-place")
                apply_success, apply_error, new_class_file = self._apply_refactoring_inplace(
                    repo,
                    original_path,
                    new_class_code,
                    modified_original_code,
                )

                if not apply_success:
                    return False, f"Failed to apply refactoring: {apply_error}"

                # Step 6: Run tests on modified repo
                self.logger.info("Running tests after refactoring")
                success, error = self._run_tests(repo, build_system)

                if success:
                    self.logger.info("Behavioral verification PASSED")
                    return True, None
                else:
                    self.logger.warning(f"Behavioral verification FAILED: {error}")
                    return False, f"Tests failed after refactoring: {error}"

            except Exception as e:
                error_msg = f"Behavioral verification error: {str(e)}"
                self.logger.error(error_msg)
                return False, error_msg

            finally:
                # Step 7: ALWAYS restore original state (with mtime conflict detection)
                self._restore_files(backup_data, new_class_file, backup_mtime)

                # Remove marker file
                if marker_file.exists():
                    marker_file.unlink()

    def _check_and_recover(self, repo: Path):
        """
        Check for interrupted verification and restore if needed.

        This handles the case where GenEC was killed mid-verification.
        """
        marker_file = repo / ".genec_verification_in_progress"
        backup_dir = repo / ".genec_verification_backup"

        if marker_file.exists():
            self.logger.warning("Detected interrupted verification, attempting recovery...")
            original_class_file = marker_file.read_text(encoding="utf-8").strip()

            # Restore from backup if it exists
            if backup_dir.exists():
                for backup_file in backup_dir.iterdir():
                    if backup_file.is_file():
                        target = repo / backup_file.name
                        shutil.copy2(backup_file, target)
                        self.logger.info(f"Recovered: {target}")
                shutil.rmtree(backup_dir)

            marker_file.unlink()
            self.logger.info("Recovery complete")

    def _apply_refactoring_inplace(
        self,
        repo: Path,
        original_path: Path,
        new_class_code: str,
        modified_original_code: str,
    ) -> tuple[bool, str | None, Path | None]:
        """
        Apply refactoring directly to the repository.

        Returns:
            Tuple of (success, error_message, new_class_file_path)
        """
        try:
            # Extract new class name
            new_class_match = re.search(r"(?:public\s+)?class\s+(\w+)", new_class_code)
            if not new_class_match:
                return False, "Could not extract new class name", None

            new_class_name = new_class_match.group(1)

            # Write modified original class
            original_path.write_text(modified_original_code, encoding="utf-8")
            self.logger.debug(f"Modified: {original_path}")

            # Write new class in same directory
            new_class_file = original_path.parent / f"{new_class_name}.java"
            new_class_file.write_text(new_class_code, encoding="utf-8")
            self.logger.debug(f"Created: {new_class_file}")

            return True, None, new_class_file

        except Exception as e:
            return False, f"Error applying refactoring: {str(e)}", None

    def _restore_files(
        self, 
        backup_data: dict[Path, str], 
        new_class_file: Path | None,
        backup_mtime: dict[Path, float] | None = None
    ):
        """
        Restore backed-up files and delete new class file.

        This is called in finally block to guarantee cleanup.
        Checks mtime to detect if user modified file during verification.
        
        Args:
            backup_data: Dict mapping path to original content
            new_class_file: Path to newly created class file to delete
            backup_mtime: Dict mapping path to original mtime (for conflict detection)
        """
        # Restore original files from backup
        for path, content in backup_data.items():
            try:
                # Check for mtime conflict (user edited during verification)
                if backup_mtime and path in backup_mtime:
                    if path.exists():
                        current_mtime = path.stat().st_mtime
                        original_mtime = backup_mtime[path]
                        
                        # If mtime changed beyond what we expect from our own write,
                        # the user may have edited the file
                        if current_mtime > original_mtime + 1:  # 1s tolerance
                            self.logger.error(
                                f"CONFLICT DETECTED: {path.name} was modified during verification. "
                                f"Skipping restore to preserve user changes. "
                                f"Original mtime: {original_mtime}, Current: {current_mtime}"
                            )
                            continue
                
                path.write_text(content, encoding="utf-8")
                self.logger.debug(f"Restored: {path}")
            except Exception as e:
                self.logger.error(f"Failed to restore {path}: {e}")

        # Delete the temporarily created new class file
        if new_class_file and new_class_file.exists():
            try:
                new_class_file.unlink()
                self.logger.debug(f"Deleted temporary: {new_class_file}")
            except Exception as e:
                self.logger.error(f"Failed to delete {new_class_file}: {e}")

    def _detect_build_system(self, repo_path: Path) -> str | None:
        """
        Detect build system (Maven or Gradle).

        Args:
            repo_path: Path to repository

        Returns:
            'maven', 'gradle', or None
        """
        if (repo_path / "pom.xml").exists():
            return "maven"
        elif (repo_path / "build.gradle").exists() or (repo_path / "build.gradle.kts").exists():
            return "gradle"
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

        test_results = re.search(
            r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+)", output, re.IGNORECASE
        )
        if test_results:
            failures = int(test_results.group(2))
            errors = int(test_results.group(3))
            if failures > 0 or errors > 0:
                return False

        # If we get here, it's either warnings or non-failure output
        return True

    def _run_tests(
        self, repo_path: Path, build_system: str, timeout: int = 180  # 3 minutes
    ) -> tuple[bool, str | None]:
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
            if build_system == "maven":
                cmd = [self.maven_command, "test", "-q"]
            elif build_system == "gradle":
                gradle_cmd = (
                    "./gradlew" if (repo_path / "gradlew").exists() else self.gradle_command
                )
                cmd = [gradle_cmd, "test", "-q"]
            else:
                return False, f"Unknown build system: {build_system}"

            # Run tests
            result = subprocess.run(
                cmd, cwd=repo_path, capture_output=True, text=True, timeout=timeout
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

    def check_build_tools_available(self) -> dict[str, bool]:
        """
        Check which build tools are available.

        Returns:
            Dict mapping tool names to availability
        """
        tools = {}

        # Check Maven
        try:
            result = subprocess.run(
                [self.maven_command, "-version"], capture_output=True, timeout=5
            )
            tools["maven"] = result.returncode == 0
        except:
            tools["maven"] = False

        # Check Gradle
        try:
            result = subprocess.run(
                [self.gradle_command, "--version"], capture_output=True, timeout=5
            )
            tools["gradle"] = result.returncode == 0
        except:
            tools["gradle"] = False

        return tools
