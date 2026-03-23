"""Tests for EquivalenceChecker."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from genec.verification.equivalence_checker import (
    EquivalenceChecker,
    EquivalenceResult,
    TestResult,
)


@pytest.fixture
def checker():
    """Create an EquivalenceChecker with default settings."""
    return EquivalenceChecker(build_tool="maven", timeout=60)


@pytest.fixture
def repo(tmp_path):
    """Create a fake Maven repo with a test file."""
    (tmp_path / "pom.xml").write_text("<project/>")
    # Source file
    src_dir = tmp_path / "src" / "main" / "java" / "com" / "example"
    src_dir.mkdir(parents=True)
    original = src_dir / "GodClass.java"
    original.write_text("public class GodClass { /* original */ }")
    # Test file
    test_dir = tmp_path / "src" / "test" / "java" / "com" / "example"
    test_dir.mkdir(parents=True)
    test_file = test_dir / "GodClassTest.java"
    test_file.write_text("public class GodClassTest { @Test void test() {} }")
    return tmp_path


@pytest.fixture
def cluster():
    """Create a minimal Cluster for testing."""
    from genec.core.cluster_detector import Cluster

    return Cluster(id=0, member_names=["methodA", "fieldX"])


@pytest.fixture
def suggestion(cluster):
    """Create a minimal RefactoringSuggestion for testing."""
    from genec.core.llm_interface import RefactoringSuggestion

    return RefactoringSuggestion(
        cluster_id=0,
        proposed_class_name="ExtractedClass",
        rationale="High cohesion subgroup",
        new_class_code="public class ExtractedClass { int x; }",
        modified_original_code="public class GodClass { /* modified */ }",
        cluster=cluster,
    )


class TestEquivalenceChecker:
    def test_equivalent_when_same_results(self, checker, repo, cluster, suggestion):
        """Same pass/fail counts before and after = equivalent."""
        original_file = "src/main/java/com/example/GodClass.java"
        refactored_files = {
            "src/main/java/com/example/GodClass.java": "public class GodClass { /* modified */ }",
            "src/main/java/com/example/ExtractedClass.java": "public class ExtractedClass { int x; }",
        }

        with patch("genec.verification.equivalence_checker.subprocess.run") as mock_run:
            # Both original and refactored tests pass
            mock_run.return_value = MagicMock(
                returncode=0, stdout="Tests passed", stderr=""
            )
            result = checker.check_equivalence(
                original_file, refactored_files, str(repo), cluster, suggestion
            )

        assert result.is_equivalent is True
        assert result.tests_run >= 1
        assert result.tests_passed_original == result.tests_passed_refactored
        assert result.differing_tests == []

    def test_not_equivalent_when_new_failures(self, checker, repo, cluster, suggestion):
        """New test failures after refactoring = not equivalent."""
        original_file = "src/main/java/com/example/GodClass.java"
        refactored_files = {
            "src/main/java/com/example/GodClass.java": "public class GodClass { /* modified */ }",
            "src/main/java/com/example/ExtractedClass.java": "public class ExtractedClass { int x; }",
        }

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Original tests pass
                return MagicMock(returncode=0, stdout="Tests passed", stderr="")
            else:
                # Refactored tests fail
                return MagicMock(
                    returncode=1, stdout="", stderr="BUILD FAILURE"
                )

        with patch("genec.verification.equivalence_checker.subprocess.run") as mock_run:
            mock_run.side_effect = side_effect
            result = checker.check_equivalence(
                original_file, refactored_files, str(repo), cluster, suggestion
            )

        assert result.is_equivalent is False
        assert len(result.differing_tests) > 0

    def test_handles_no_tests(self, checker, tmp_path, cluster, suggestion):
        """Should handle case where no tests exist."""
        (tmp_path / "pom.xml").write_text("<project/>")
        src_dir = tmp_path / "src" / "main" / "java" / "com" / "example"
        src_dir.mkdir(parents=True)
        original = src_dir / "GodClass.java"
        original.write_text("public class GodClass { }")

        original_file = "src/main/java/com/example/GodClass.java"
        refactored_files = {
            "src/main/java/com/example/GodClass.java": "public class GodClass { /* modified */ }",
        }

        result = checker.check_equivalence(
            original_file, refactored_files, str(tmp_path), cluster, suggestion
        )

        # No tests => assumed equivalent
        assert result.is_equivalent is True
        assert result.tests_run == 0
        assert result.error_message == "No tests found"

    def test_backup_and_restore(self, checker, repo, cluster, suggestion):
        """Files should be backed up before and restored after checking."""
        original_file = "src/main/java/com/example/GodClass.java"
        original_path = repo / original_file
        original_content = original_path.read_text()
        new_class_path = repo / "src" / "main" / "java" / "com" / "example" / "ExtractedClass.java"

        refactored_files = {
            "src/main/java/com/example/GodClass.java": "public class GodClass { /* modified */ }",
            "src/main/java/com/example/ExtractedClass.java": "public class ExtractedClass { int x; }",
        }

        with patch("genec.verification.equivalence_checker.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            checker.check_equivalence(
                original_file, refactored_files, str(repo), cluster, suggestion
            )

        # Original file should be restored
        assert original_path.read_text() == original_content
        # Created file should be removed
        assert not new_class_path.exists()

    def test_compare_test_results_all_pass(self, checker):
        """Both passing = equivalent."""
        original = {"TestA": TestResult(test_name="TestA", passed=True)}
        refactored = {"TestA": TestResult(test_name="TestA", passed=True)}
        is_eq, differing = checker._compare_test_results(original, refactored)
        assert is_eq is True
        assert differing == []

    def test_compare_test_results_mismatch(self, checker):
        """Pass/fail mismatch = not equivalent."""
        original = {"TestA": TestResult(test_name="TestA", passed=True)}
        refactored = {"TestA": TestResult(test_name="TestA", passed=False)}
        is_eq, differing = checker._compare_test_results(original, refactored)
        assert is_eq is False
        assert len(differing) == 1

    def test_compare_test_results_missing_in_refactored(self, checker):
        """Missing test in refactored results = not equivalent."""
        original = {"TestA": TestResult(test_name="TestA", passed=True)}
        refactored = {}
        is_eq, differing = checker._compare_test_results(original, refactored)
        assert is_eq is False
        assert len(differing) == 1
        assert "missing" in differing[0]

    def test_restore_removes_created_files(self, checker, tmp_path):
        """_restore_backup should remove files that were created during refactoring."""
        created = tmp_path / "NewFile.java"
        created.write_text("public class NewFile {}")

        checker._restore_backup(
            backup={}, created_files=[str(created)], repo_path=str(tmp_path)
        )

        assert not created.exists()

    def test_restore_restores_backed_up_content(self, checker, tmp_path):
        """_restore_backup should restore original file content."""
        target = tmp_path / "Original.java"
        target.write_text("modified content")

        checker._restore_backup(
            backup={str(target): "original content"},
            created_files=[],
            repo_path=str(tmp_path),
        )

        assert target.read_text() == "original content"

    def test_discover_tests_finds_standard_patterns(self, checker, repo):
        """Should discover test files matching standard naming patterns."""
        tests = checker._discover_tests(
            "src/main/java/com/example/GodClass.java", str(repo)
        )
        assert len(tests) >= 1
        assert any("GodClassTest" in t for t in tests)

    def test_handles_path_resolution(self, checker, repo, cluster, suggestion):
        """Should handle both relative and absolute class file paths."""
        # Relative path
        refactored_files = {
            "src/main/java/com/example/GodClass.java": "public class GodClass {}",
        }
        with patch("genec.verification.equivalence_checker.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = checker.check_equivalence(
                "src/main/java/com/example/GodClass.java",
                refactored_files,
                str(repo),
                cluster,
                suggestion,
            )
        assert result is not None
