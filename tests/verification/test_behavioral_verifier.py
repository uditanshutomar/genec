"""Tests for BehavioralVerifier."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from genec.verification.behavioral_verifier import BehavioralVerifier


@pytest.fixture
def verifier():
    """Create a BehavioralVerifier with default settings."""
    return BehavioralVerifier(incremental_tests=False, check_coverage=False)


@pytest.fixture
def repo(tmp_path):
    """Create a fake Maven repo structure."""
    (tmp_path / "pom.xml").write_text("<project/>")
    src_dir = tmp_path / "src" / "main" / "java" / "com" / "example"
    src_dir.mkdir(parents=True)
    original = src_dir / "GodClass.java"
    original.write_text("public class GodClass { /* original */ }")
    return tmp_path


class TestBehavioralVerifier:
    def test_passes_when_tests_pass(self, verifier, repo):
        """Should return pass when subprocess reports 0 failures."""
        original_file = "src/main/java/com/example/GodClass.java"
        new_code = "public class Extracted { int x; }"
        modified_code = "public class GodClass { /* modified */ }"

        with patch("genec.verification.behavioral_verifier.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            success, error = verifier.verify(
                original_file, new_code, modified_code, str(repo)
            )

        assert success is True
        assert error is None

    def test_fails_when_tests_fail(self, verifier, repo):
        """Should return fail when subprocess reports test failures."""
        original_file = "src/main/java/com/example/GodClass.java"
        new_code = "public class Extracted { int x; }"
        modified_code = "public class GodClass { /* modified */ }"

        with patch("genec.verification.behavioral_verifier.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="BUILD FAILURE\nTests run: 5, Failures: 2, Errors: 0",
            )
            success, error = verifier.verify(
                original_file, new_code, modified_code, str(repo)
            )

        assert success is False
        assert error is not None
        assert "Tests failed" in error or "BUILD FAILURE" in error

    def test_restores_files_after_verification(self, verifier, repo):
        """Original files should be restored after test run."""
        original_file = "src/main/java/com/example/GodClass.java"
        original_path = repo / original_file
        original_content = original_path.read_text()

        new_code = "public class Extracted { int x; }"
        modified_code = "public class GodClass { /* modified */ }"
        new_class_path = original_path.parent / "Extracted.java"

        with patch("genec.verification.behavioral_verifier.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            verifier.verify(original_file, new_code, modified_code, str(repo))

        # Original file should be restored to its initial content
        assert original_path.read_text() == original_content
        # New class file should be deleted
        assert not new_class_path.exists()
        # Marker file should be removed
        assert not (repo / ".genec_verification_in_progress").exists()
        # Backup dir should be cleaned up
        assert not (repo / ".genec_verification_backup").exists()

    def test_handles_no_build_system(self, verifier, repo):
        """Should skip gracefully when no build system is detected."""
        # Remove pom.xml so no build system is detected
        (repo / "pom.xml").unlink()

        original_file = "src/main/java/com/example/GodClass.java"
        new_code = "public class Extracted { int x; }"
        modified_code = "public class GodClass { /* modified */ }"

        success, message = verifier.verify(
            original_file, new_code, modified_code, str(repo)
        )
        assert success is True
        assert "no build system" in message.lower()

    def test_handles_subprocess_timeout(self, verifier, repo):
        """Should handle test execution timeout gracefully."""
        original_file = "src/main/java/com/example/GodClass.java"
        new_code = "public class Extracted { int x; }"
        modified_code = "public class GodClass { /* modified */ }"

        with patch("genec.verification.behavioral_verifier.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="mvn test", timeout=180)
            success, error = verifier.verify(
                original_file, new_code, modified_code, str(repo)
            )

        assert success is False
        assert error is not None
        assert "timeout" in error.lower()

    def test_handles_build_failure(self, verifier, repo):
        """Should handle case where project doesn't build (build tool not found)."""
        original_file = "src/main/java/com/example/GodClass.java"
        new_code = "public class Extracted { int x; }"
        modified_code = "public class GodClass { /* modified */ }"

        with patch("genec.verification.behavioral_verifier.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("mvn not found")
            success, error = verifier.verify(
                original_file, new_code, modified_code, str(repo)
            )

        assert success is False
        assert error is not None
        assert "not found" in error.lower() or "Build tool" in error

    def test_detect_build_system_maven(self, verifier, tmp_path):
        """Should detect Maven when pom.xml exists."""
        (tmp_path / "pom.xml").touch()
        assert verifier._detect_build_system(tmp_path) == "maven"

    def test_detect_build_system_gradle(self, verifier, tmp_path):
        """Should detect Gradle when build.gradle exists."""
        (tmp_path / "build.gradle").touch()
        assert verifier._detect_build_system(tmp_path) == "gradle"

    def test_detect_build_system_none(self, verifier, tmp_path):
        """Should return None when no build system is found."""
        assert verifier._detect_build_system(tmp_path) is None

    def test_only_contains_warnings_empty_output(self, verifier):
        """Empty output should be treated as warnings only."""
        assert verifier._only_contains_warnings("") is True
        assert verifier._only_contains_warnings("   ") is True

    def test_only_contains_warnings_with_failure(self, verifier):
        """Output with BUILD FAILURE should not be treated as warnings."""
        assert verifier._only_contains_warnings("BUILD FAILURE") is False

    def test_only_contains_warnings_success_summary(self, verifier):
        """Tests run with 0 failures and 0 errors is success even with keywords."""
        output = "Tests run: 10, Failures: 0, Errors: 0, Skipped: 1"
        assert verifier._only_contains_warnings(output) is True

    def test_restores_files_even_on_exception(self, verifier, repo):
        """Files should be restored even when an exception occurs during testing."""
        original_file = "src/main/java/com/example/GodClass.java"
        original_path = repo / original_file
        original_content = original_path.read_text()

        new_code = "public class Extracted { int x; }"
        modified_code = "public class GodClass { /* modified */ }"

        with patch("genec.verification.behavioral_verifier.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("Unexpected error")
            success, error = verifier.verify(
                original_file, new_code, modified_code, str(repo)
            )

        assert success is False
        # File should still be restored
        assert original_path.read_text() == original_content
