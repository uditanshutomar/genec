"""Unit tests for RefactoringApplicator."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from genec.core.llm_interface import RefactoringSuggestion
from genec.core.refactoring_applicator import (
    RefactoringApplication,
    RefactoringApplicator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_suggestion(
    class_name: str = "ExtractedClass",
    new_code: str = "public class ExtractedClass {}",
    modified_code: str = "public class Original { ExtractedClass e; }",
) -> RefactoringSuggestion:
    return RefactoringSuggestion(
        cluster_id=0,
        proposed_class_name=class_name,
        rationale="test",
        new_class_code=new_code,
        modified_original_code=modified_code,
    )


def _setup_original(tmp_path: Path, filename: str = "Original.java", content: str = "public class Original {}") -> Path:
    """Create a fake original Java file inside tmp_path and return its path."""
    f = tmp_path / filename
    f.write_text(content)
    return f


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRefactoringApplicator:
    """Core apply/rollback tests."""

    @patch("genec.core.refactoring_applicator.GitWrapper")
    def test_writes_new_class_file(self, _mock_git, tmp_path):
        """Should create the extracted class file in the same directory."""
        original = _setup_original(tmp_path)
        suggestion = _make_suggestion()

        applicator = RefactoringApplicator(
            create_backups=False,
            backup_dir=str(tmp_path / "backups"),
            enable_git=False,
        )

        result = applicator.apply_refactoring(
            suggestion=suggestion,
            original_class_file=str(original),
            repo_path=str(tmp_path),
            create_branch=False,
        )

        assert result.success is True
        new_path = tmp_path / "ExtractedClass.java"
        assert new_path.exists()
        assert new_path.read_text() == suggestion.new_class_code

    @patch("genec.core.refactoring_applicator.GitWrapper")
    def test_modifies_original_file(self, _mock_git, tmp_path):
        """Should update the original class file with modified_original_code."""
        original = _setup_original(tmp_path)
        suggestion = _make_suggestion()

        applicator = RefactoringApplicator(
            create_backups=False,
            backup_dir=str(tmp_path / "backups"),
            enable_git=False,
        )

        applicator.apply_refactoring(
            suggestion=suggestion,
            original_class_file=str(original),
            repo_path=str(tmp_path),
            create_branch=False,
        )

        assert original.read_text() == suggestion.modified_original_code

    @patch("genec.core.refactoring_applicator.GitWrapper")
    def test_rejects_empty_new_class_code(self, _mock_git, tmp_path):
        """Should return failure when new_class_code is empty."""
        original = _setup_original(tmp_path)
        suggestion = _make_suggestion(new_code="")

        applicator = RefactoringApplicator(
            create_backups=False,
            backup_dir=str(tmp_path / "backups"),
            enable_git=False,
        )

        result = applicator.apply_refactoring(
            suggestion=suggestion,
            original_class_file=str(original),
            repo_path=str(tmp_path),
            create_branch=False,
        )

        assert result.success is False
        assert "empty" in result.error_message.lower()

    @patch("genec.core.refactoring_applicator.GitWrapper")
    def test_rejects_none_new_class_code(self, _mock_git, tmp_path):
        """Should return failure when new_class_code is None."""
        original = _setup_original(tmp_path)
        suggestion = _make_suggestion(new_code=None)

        applicator = RefactoringApplicator(
            create_backups=False,
            backup_dir=str(tmp_path / "backups"),
            enable_git=False,
        )

        result = applicator.apply_refactoring(
            suggestion=suggestion,
            original_class_file=str(original),
            repo_path=str(tmp_path),
            create_branch=False,
        )

        assert result.success is False

    @patch("genec.core.refactoring_applicator.GitWrapper")
    def test_rejects_empty_modified_original_code(self, _mock_git, tmp_path):
        """Should return failure when modified_original_code is empty."""
        original = _setup_original(tmp_path)
        suggestion = _make_suggestion(modified_code="   ")

        applicator = RefactoringApplicator(
            create_backups=False,
            backup_dir=str(tmp_path / "backups"),
            enable_git=False,
        )

        result = applicator.apply_refactoring(
            suggestion=suggestion,
            original_class_file=str(original),
            repo_path=str(tmp_path),
            create_branch=False,
        )

        assert result.success is False
        assert "empty" in result.error_message.lower()

    @patch("genec.core.refactoring_applicator.GitWrapper")
    def test_creates_package_directories(self, _mock_git, tmp_path):
        """New class file should be created even when parent dirs exist only at original location."""
        # The applicator places the new class in the same dir as the original.
        # If the original is in a deep path, parent dirs should already exist.
        pkg_dir = tmp_path / "src" / "com" / "example"
        pkg_dir.mkdir(parents=True)
        original = _setup_original(pkg_dir, "Original.java")

        suggestion = _make_suggestion(class_name="Helper")

        applicator = RefactoringApplicator(
            create_backups=False,
            backup_dir=str(tmp_path / "backups"),
            enable_git=False,
        )

        result = applicator.apply_refactoring(
            suggestion=suggestion,
            original_class_file=str(original),
            repo_path=str(tmp_path),
            create_branch=False,
        )

        assert result.success is True
        assert (pkg_dir / "Helper.java").exists()

    @patch("genec.core.refactoring_applicator.GitWrapper")
    def test_dry_run_does_not_write(self, _mock_git, tmp_path):
        """dry_run=True should not create/modify any files."""
        original = _setup_original(tmp_path)
        original_content = original.read_text()
        suggestion = _make_suggestion()

        applicator = RefactoringApplicator(
            create_backups=False,
            backup_dir=str(tmp_path / "backups"),
            enable_git=False,
        )

        result = applicator.apply_refactoring(
            suggestion=suggestion,
            original_class_file=str(original),
            repo_path=str(tmp_path),
            dry_run=True,
            create_branch=False,
        )

        assert result.success is True
        # Original file should be unchanged
        assert original.read_text() == original_content
        # New file should NOT exist
        assert not (tmp_path / "ExtractedClass.java").exists()


class TestBackup:
    """Tests for backup creation and rollback."""

    @patch("genec.core.refactoring_applicator.GitWrapper")
    def test_creates_backup(self, _mock_git, tmp_path):
        """When create_backups=True a backup of the original should be created."""
        original = _setup_original(tmp_path)
        suggestion = _make_suggestion()
        backup_dir = tmp_path / "backups"

        applicator = RefactoringApplicator(
            create_backups=True,
            backup_dir=str(backup_dir),
            enable_git=False,
        )

        result = applicator.apply_refactoring(
            suggestion=suggestion,
            original_class_file=str(original),
            repo_path=str(tmp_path),
            create_branch=False,
        )

        assert result.success is True
        assert result.backup_path is not None
        assert os.path.exists(result.backup_path)
        # Backup content should match the original (pre-modification) content
        assert Path(result.backup_path).read_text() == "public class Original {}"

    @patch("genec.core.refactoring_applicator.GitWrapper")
    def test_rollback_restores_original(self, _mock_git, tmp_path):
        """rollback_refactoring should restore the original and delete the new file."""
        original = _setup_original(tmp_path)
        suggestion = _make_suggestion()
        backup_dir = tmp_path / "backups"

        applicator = RefactoringApplicator(
            create_backups=True,
            backup_dir=str(backup_dir),
            enable_git=False,
        )

        result = applicator.apply_refactoring(
            suggestion=suggestion,
            original_class_file=str(original),
            repo_path=str(tmp_path),
            create_branch=False,
        )

        assert result.success is True

        # Now rollback
        rollback_ok = applicator.rollback_refactoring(result)
        assert rollback_ok is True
        # Original should be restored
        assert original.read_text() == "public class Original {}"
        # New file should be deleted
        assert not (tmp_path / "ExtractedClass.java").exists()


class TestRevertChanges:
    """Tests for revert_changes (convenience wrapper)."""

    @patch("genec.core.refactoring_applicator.GitWrapper")
    def test_revert_with_no_previous_application(self, _mock_git, tmp_path):
        applicator = RefactoringApplicator(
            create_backups=False,
            backup_dir=str(tmp_path / "backups"),
            enable_git=False,
        )
        assert applicator.revert_changes() is False


class TestFileAlreadyExists:
    """Edge case: new class file already exists on disk."""

    @patch("genec.core.refactoring_applicator.GitWrapper")
    def test_rejects_if_file_exists(self, _mock_git, tmp_path):
        original = _setup_original(tmp_path)
        # Pre-create the target file
        (tmp_path / "ExtractedClass.java").write_text("existing")

        suggestion = _make_suggestion()
        applicator = RefactoringApplicator(
            create_backups=False,
            backup_dir=str(tmp_path / "backups"),
            enable_git=False,
        )

        result = applicator.apply_refactoring(
            suggestion=suggestion,
            original_class_file=str(original),
            repo_path=str(tmp_path),
            create_branch=False,
        )

        assert result.success is False
        assert "already exists" in result.error_message


class TestComputeNewClassPath:
    """Tests for _compute_new_class_path helper."""

    def test_places_in_same_directory(self, tmp_path):
        applicator = RefactoringApplicator(
            create_backups=False,
            backup_dir=str(tmp_path / "backups"),
            enable_git=False,
        )
        original = tmp_path / "src" / "com" / "example" / "Original.java"
        result = applicator._compute_new_class_path(original, "Helper", str(tmp_path))
        assert result == original.parent / "Helper.java"


class TestCleanupBackups:
    """Tests for cleanup_backups."""

    def test_keeps_only_recent(self, tmp_path):
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        # Create 7 fake backup files for the same base name
        import time
        for i in range(7):
            name = f"Original_20260301_00000{i}.java"
            (backup_dir / name).write_text(f"backup {i}")
            # Ensure distinct mtime
            time.sleep(0.01)

        applicator = RefactoringApplicator(
            create_backups=True,
            backup_dir=str(backup_dir),
            enable_git=False,
        )
        applicator.cleanup_backups(keep_recent=3)

        remaining = list(backup_dir.glob("*.java"))
        assert len(remaining) == 3
