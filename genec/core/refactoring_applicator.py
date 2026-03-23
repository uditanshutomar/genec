"""
Refactoring Applicator - Applies generated refactorings to source files.

This module is responsible for writing refactored code to the filesystem,
creating backups, and managing the refactoring application process.
"""

import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from genec.core.git_wrapper import GitWrapper, generate_commit_message  # NEW
from genec.core.llm_interface import RefactoringSuggestion
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class RefactoringApplication:
    """Result of applying a refactoring."""

    success: bool
    new_class_path: str | None = None
    original_class_path: str | None = None
    backup_path: str | None = None
    commit_hash: str | None = None  # NEW
    branch_name: str | None = None  # NEW
    error_message: str | None = None


class RefactoringApplicator:
    """
    Applies refactoring suggestions to source files.

    Features:
    - Creates backups before modifying files
    - Writes new extracted class
    - Updates original class
    - Rollback support if verification fails
    """

    def __init__(
        self, create_backups: bool = True, backup_dir: str | None = None, enable_git: bool = True
    ):
        """
        Initialize refactoring applicator.

        Args:
            create_backups: Whether to create backups before modifying files
            backup_dir: Directory for backups (default: .genec_backups)
            enable_git: Enable Git integration for atomic commits (NEW)
        """
        self.create_backups = create_backups
        self.backup_dir = Path(backup_dir) if backup_dir else Path(".genec_backups")
        self.backup_dir.mkdir(exist_ok=True)
        self.enable_git = enable_git  # NEW
        self.git_wrapper = None  # Will be initialized when needed
        self.logger = get_logger(self.__class__.__name__)
        self._last_application: RefactoringApplication | None = None  # Track last application for revert

    def revert_changes(self) -> bool:
        """
        Revert the last applied refactoring.
        
        Returns:
            True if revert successful, False otherwise
        """
        if self._last_application is None:
            self.logger.warning("No previous application to revert")
            return False
        
        success = self.rollback_refactoring(self._last_application)
        if success:
            self._last_application = None
        return success

    def apply_refactoring(
        self,
        suggestion: RefactoringSuggestion,
        original_class_file: str,
        repo_path: str,
        dry_run: bool = False,
        create_branch: bool = True,  # NEW
    ) -> RefactoringApplication:
        """
        Apply a refactoring suggestion to the filesystem.

        Args:
            suggestion: The refactoring suggestion to apply
            original_class_file: Path to the original class file
            repo_path: Path to repository root
            dry_run: If True, don't actually write files
            create_branch: Create Git branch for refactoring (NEW)

        Returns:
            RefactoringApplication result
        """
        self.logger.info(f"Applying refactoring: {suggestion.proposed_class_name}")

        # Initialize Git wrapper if enabled
        if self.enable_git and self.git_wrapper is None:
            self.git_wrapper = GitWrapper(repo_path)

        original_path = Path(original_class_file)

        # Compute paths
        new_class_path = self._compute_new_class_path(
            original_path, suggestion.proposed_class_name, repo_path
        )

        if dry_run:
            self.logger.info(f"[DRY RUN] Would create: {new_class_path}")
            self.logger.info(f"[DRY RUN] Would modify: {original_path}")
            return RefactoringApplication(
                success=True,
                new_class_path=str(new_class_path),
                original_class_path=str(original_path),
            )

        # Create backup
        backup_path = None
        if self.create_backups:
            backup_path = self._create_backup(original_path)

        try:
            # Git: Create feature branch
            branch_name = None
            original_branch = None
            if self.enable_git and self.git_wrapper and self.git_wrapper.is_available():
                if create_branch:
                    branch_name = f"genec/refactor-{suggestion.proposed_class_name}"
                    status = self.git_wrapper.get_status()
                    original_branch = status.current_branch

                    if not self.git_wrapper.create_branch(branch_name):
                        self.logger.warning("Failed to create Git branch, continuing without")

            # Check if new class file already exists - skip if so to avoid duplicates
            if new_class_path.exists():
                self.logger.warning(
                    f"Skipping {suggestion.proposed_class_name}: file already exists at {new_class_path}"
                )
                return RefactoringApplication(
                    success=False,
                    new_class_path=str(new_class_path),
                    original_class_path=str(original_path),
                    error_message=f"File already exists: {new_class_path}",
                )

            # Validate code before writing
            if not suggestion.new_class_code or not suggestion.new_class_code.strip():
                self.logger.error("new_class_code is empty or None; aborting refactoring")
                return RefactoringApplication(
                    success=False,
                    error_message="new_class_code is empty or None",
                )
            if not suggestion.modified_original_code or not suggestion.modified_original_code.strip():
                self.logger.error("modified_original_code is empty or None; aborting refactoring")
                return RefactoringApplication(
                    success=False,
                    error_message="modified_original_code is empty or None",
                )

            # Validate generated code before writing to disk
            self._validate_code_safety(suggestion.new_class_code, "new class code")
            self._validate_code_safety(suggestion.modified_original_code, "modified original code")

            # Write new class file
            new_class_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_file(new_class_path, suggestion.new_class_code)
            self.logger.info(f"Created new class: {new_class_path}")

            # Update original class file
            self._write_file(original_path, suggestion.modified_original_code)
            self.logger.info(f"Updated original class: {original_path}")

            # Git: Create atomic commit
            commit_hash = None
            if self.enable_git and self.git_wrapper and self.git_wrapper.is_available():
                # Generate commit message
                commit_msg = generate_commit_message(
                    suggestion=suggestion, original_class_name=original_path.stem
                )

                # Create commit
                files_to_commit = [str(new_class_path), str(original_path)]
                commit_hash = self.git_wrapper.create_commit(
                    message=commit_msg, files=files_to_commit
                )

                if commit_hash:
                    self.logger.info(f"Created commit {commit_hash}")

                # Return to original branch
                if create_branch and original_branch:
                    self.git_wrapper.checkout_branch(original_branch)

            self.logger.info("Refactoring applied successfully")

            result = RefactoringApplication(
                success=True,
                new_class_path=str(new_class_path),
                original_class_path=str(original_path),
                backup_path=str(backup_path) if backup_path else None,
                commit_hash=commit_hash,
                branch_name=branch_name,
            )
            self._last_application = result  # Store for revert
            return result

        except Exception as e:
            self.logger.error(f"Failed to apply refactoring: {e}", exc_info=True)

            # Rollback: Restore from backup
            if backup_path and backup_path.exists():
                shutil.copy(backup_path, original_path)
                self.logger.info("Rolled back changes from backup")

            return RefactoringApplication(success=False, error_message=str(e))

    def rollback_refactoring(self, application: RefactoringApplication) -> bool:
        """
        Rollback a refactoring by restoring from backup.

        Args:
            application: The RefactoringApplication to rollback

        Returns:
            True if rollback successful, False otherwise
        """
        try:
            if not application.backup_path or not os.path.exists(application.backup_path):
                self.logger.warning("No backup found, cannot rollback")
                return False

            # Delete new class if it was created
            if application.new_class_path and os.path.exists(application.new_class_path):
                os.remove(application.new_class_path)
                self.logger.info(f"Deleted new class: {application.new_class_path}")

            # Restore original from backup
            if application.original_class_path:
                shutil.copy2(application.backup_path, application.original_class_path)
                self.logger.info(
                    f"Restored original from backup: {application.original_class_path}"
                )

            return True

        except Exception as e:
            self.logger.error(f"Rollback failed: {e}", exc_info=True)
            return False

    def _compute_new_class_path(
        self, original_path: Path, new_class_name: str, repo_path: str
    ) -> Path:
        """
        Compute the path for the new extracted class.

        Places it in the same directory as the original class.

        Args:
            original_path: Path to original class file
            new_class_name: Name of new class
            repo_path: Repository root path

        Returns:
            Path for new class file

        Raises:
            ValueError: If class name is not a valid Java identifier or the
                        resolved path escapes the repository root.
        """
        # Validate class name is a safe Java identifier (no path separators)
        if not new_class_name or not re.match(r'^[A-Za-z_$][A-Za-z0-9_$]*$', new_class_name):
            raise ValueError(f"Invalid Java class name: {new_class_name!r}")

        # Place new class in same directory as original
        new_file_name = f"{new_class_name}.java"
        new_path = original_path.parent / new_file_name

        # Verify path stays within repo to prevent path traversal
        if repo_path:
            repo_resolved = Path(repo_path).resolve()
            new_resolved = new_path.resolve()
            if not str(new_resolved).startswith(str(repo_resolved)):
                raise ValueError(
                    f"Generated path {new_resolved} escapes repo {repo_resolved}"
                )

        return new_path

    def _validate_code_safety(self, code: str, label: str) -> None:
        """Basic safety check on generated code before writing to disk.

        Logs warnings for suspicious patterns that could indicate
        injected or unintended code from the LLM.  This is advisory
        only -- it does not block the write.

        Args:
            code: The generated Java source code.
            label: Human-readable label for log messages (e.g. "new class code").
        """
        dangerous_patterns = [
            'Runtime.getRuntime().exec',
            'ProcessBuilder',
            'System.exit',
            'java.lang.reflect',
            'java.net.URL',
            'java.io.File("/',  # Absolute path access
        ]
        for pattern in dangerous_patterns:
            if pattern in code:
                self.logger.warning(
                    f"Suspicious pattern '{pattern}' found in {label}"
                )

    def _create_backup(self, file_path: Path) -> str:
        """
        Create a backup of a file.

        Args:
            file_path: Path to file to backup

        Returns:
            Path to backup file
        """
        # Create backup directory if it doesn't exist
        backup_dir = Path(self.backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = backup_dir / backup_name

        # Copy file to backup location
        shutil.copy2(file_path, backup_path)

        return str(backup_path)

    def _write_file(self, file_path: Path, content: str):
        """
        Write content to a file atomically.

        Uses write-to-temp-then-rename pattern to prevent partial writes.

        Args:
            file_path: Path to file
            content: Content to write
        """
        import tempfile

        # Create parent directories if they don't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: write to temp file in same directory, then rename
        # Using same directory ensures atomic rename on same filesystem
        fd, temp_path = tempfile.mkstemp(
            suffix=".tmp", prefix=f".{file_path.name}_", dir=file_path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            # Atomic rename (works on POSIX and Windows)
            os.replace(temp_path, file_path)
        except Exception as e:
            # Clean up temp file on error
            self.logger.warning(f"Failed to write file {file_path}: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    def cleanup_backups(self, keep_recent: int = 5):
        """
        Clean up old backups, keeping only the most recent ones.

        Args:
            keep_recent: Number of recent backups to keep per file
        """
        try:
            backup_dir = Path(self.backup_dir)
            if not backup_dir.exists():
                return

            # Group backups by base filename
            backups_by_file = {}
            for backup_file in backup_dir.glob("*.java"):
                # Extract base name (remove timestamp)
                parts = backup_file.stem.split("_")
                if len(parts) >= 3:  # name_YYYYMMDD_HHMMSS
                    base_name = "_".join(parts[:-2])
                    if base_name not in backups_by_file:
                        backups_by_file[base_name] = []
                    backups_by_file[base_name].append(backup_file)

            # Keep only recent backups
            for base_name, backups in backups_by_file.items():
                # Sort by modification time (newest first)
                backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)

                # Delete old backups
                for old_backup in backups[keep_recent:]:
                    old_backup.unlink()
                    self.logger.info(f"Deleted old backup: {old_backup}")

        except Exception as e:
            self.logger.warning(f"Failed to cleanup backups: {e}")
