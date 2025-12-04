"""
Enhanced Rollback Manager for GenEC.

Provides comprehensive rollback capabilities including:
- Git-based rollback (revert)
- Timestamped backup management
- Metadata tracking
- Recovery mechanisms
"""

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from genec.core.git_wrapper import GitWrapper
from genec.core.refactoring_applicator import RefactoringApplication
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class BackupMetadata:
    """Metadata for a backup."""

    backup_id: str
    timestamp: str
    original_files: list[str]
    new_files: list[str]
    commit_hash: str | None = None
    branch_name: str | None = None
    refactoring_name: str = ""
    can_git_revert: bool = False


@dataclass
class RollbackResult:
    """Result of rollback operation."""

    success: bool
    method_used: str  # "git_revert", "filesystem", "backup"
    files_restored: list[str]
    error_message: str | None = None


class RollbackManager:
    """
    Manages rollback operations for refactorings.

    Supports multiple rollback strategies:
    1. Git revert (preferred)
    2. Filesystem rollback
    3. Backup restoration
    """

    def __init__(self, backup_dir: str = ".genec_backups", metadata_dir: str = ".genec_metadata"):
        """
        Initialize rollback manager.

        Args:
            backup_dir: Directory for file backups
            metadata_dir: Directory for metadata storage
        """
        self.backup_dir = Path(backup_dir)
        self.metadata_dir = Path(metadata_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.metadata_dir.mkdir(exist_ok=True)
        self.logger = get_logger(self.__class__.__name__)

    def save_application_metadata(
        self, application: RefactoringApplication, refactoring_name: str
    ) -> str:
        """
        Save metadata for a refactoring application.

        Args:
            application: RefactoringApplication to save
            refactoring_name: Name of refactoring

        Returns:
            Backup ID
        """
        backup_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        metadata = BackupMetadata(
            backup_id=backup_id,
            timestamp=datetime.now().isoformat(),
            original_files=(
                [application.original_class_path] if application.original_class_path else []
            ),
            new_files=[application.new_class_path] if application.new_class_path else [],
            commit_hash=application.commit_hash,
            branch_name=application.branch_name,
            refactoring_name=refactoring_name,
            can_git_revert=application.commit_hash is not None,
        )

        # Save metadata
        metadata_file = self.metadata_dir / f"{backup_id}.json"
        with open(metadata_file, "w") as f:
            json.dump(asdict(metadata), f, indent=2)

        self.logger.info(f"Saved metadata: {backup_id}")
        return backup_id

    def load_metadata(self, backup_id: str) -> BackupMetadata | None:
        """Load metadata for a backup."""
        metadata_file = self.metadata_dir / f"{backup_id}.json"

        if not metadata_file.exists():
            return None

        with open(metadata_file) as f:
            data = json.load(f)

        return BackupMetadata(**data)

    def list_backups(self) -> list[BackupMetadata]:
        """List all available backups."""
        backups = []

        for metadata_file in self.metadata_dir.glob("*.json"):
            try:
                with open(metadata_file) as f:
                    data = json.load(f)
                backups.append(BackupMetadata(**data))
            except Exception as e:
                self.logger.warning(f"Failed to load {metadata_file}: {e}")

        # Sort by timestamp (newest first)
        backups.sort(key=lambda b: b.timestamp, reverse=True)
        return backups

    def rollback(
        self,
        backup_id: str | None = None,
        commit_hash: str | None = None,
        repo_path: str | None = None,
        prefer_git: bool = True,
    ) -> RollbackResult:
        """
        Rollback a refactoring.

        Args:
            backup_id: Backup ID to restore
            commit_hash: Git commit to revert
            repo_path: Repository path (for Git operations)
            prefer_git: Prefer Git revert over filesystem rollback

        Returns:
            RollbackResult
        """
        # Strategy 1: Git revert (if available and preferred)
        if prefer_git and commit_hash and repo_path:
            result = self._git_revert(commit_hash, repo_path)
            if result.success:
                return result
            self.logger.warning("Git revert failed, falling back to filesystem")

        # Strategy 2: Filesystem rollback using metadata
        if backup_id:
            metadata = self.load_metadata(backup_id)
            if metadata:
                return self._filesystem_rollback(metadata)

        # Strategy 3: Backup restoration
        return RollbackResult(
            success=False,
            method_used="none",
            files_restored=[],
            error_message="No valid rollback method available",
        )

    def _git_revert(self, commit_hash: str, repo_path: str) -> RollbackResult:
        """
        Rollback using Git revert.

        Args:
            commit_hash: Commit to revert
            repo_path: Repository path

        Returns:
            RollbackResult
        """
        try:
            git_wrapper = GitWrapper(repo_path)

            if not git_wrapper.is_available():
                return RollbackResult(
                    success=False,
                    method_used="git_revert",
                    files_restored=[],
                    error_message="Git not available",
                )

            # Revert the commit
            success = git_wrapper.revert_commit(commit_hash)

            if success:
                # Get changed files
                changed_files = git_wrapper.get_changed_files()

                self.logger.info(f"Successfully reverted commit {commit_hash}")
                return RollbackResult(
                    success=True, method_used="git_revert", files_restored=changed_files
                )

            return RollbackResult(
                success=False,
                method_used="git_revert",
                files_restored=[],
                error_message="Git revert command failed",
            )

        except Exception as e:
            return RollbackResult(
                success=False, method_used="git_revert", files_restored=[], error_message=str(e)
            )

    def _filesystem_rollback(self, metadata: BackupMetadata) -> RollbackResult:
        """
        Rollback by deleting new files and restoring from backup.

        Args:
            metadata: Backup metadata

        Returns:
            RollbackResult
        """
        try:
            files_restored = []

            # Delete new files
            for new_file in metadata.new_files:
                path = Path(new_file)
                if path.exists():
                    path.unlink()
                    files_restored.append(new_file)
                    self.logger.info(f"Deleted new file: {new_file}")

            # Restore original files from backup
            for original_file in metadata.original_files:
                # Find backup file
                backup_pattern = f"*{Path(original_file).stem}*.java"
                backups = list(self.backup_dir.glob(backup_pattern))

                if backups:
                    # Use most recent backup
                    backup_file = max(backups, key=lambda p: p.stat().st_mtime)
                    shutil.copy2(backup_file, original_file)
                    files_restored.append(original_file)
                    self.logger.info(f"Restored from backup: {original_file}")

            return RollbackResult(
                success=True, method_used="filesystem", files_restored=files_restored
            )

        except Exception as e:
            return RollbackResult(
                success=False, method_used="filesystem", files_restored=[], error_message=str(e)
            )

    def cleanup_old_backups(self, days_to_keep: int = 30):
        """
        Clean up backups older than specified days.

        Args:
            days_to_keep: Number of days to keep backups
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days_to_keep)
        deleted_count = 0

        # Clean metadata
        for metadata_file in self.metadata_dir.glob("*.json"):
            try:
                with open(metadata_file) as f:
                    data = json.load(f)

                timestamp = datetime.fromisoformat(data["timestamp"])
                if timestamp < cutoff:
                    metadata_file.unlink()
                    deleted_count += 1
            except Exception as e:
                self.logger.warning(f"Failed to process {metadata_file}: {e}")

        # Clean backups
        for backup_file in self.backup_dir.glob("*.java"):
            mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
            if mtime < cutoff:
                backup_file.unlink()
                deleted_count += 1

        if deleted_count > 0:
            self.logger.info(f"Cleaned up {deleted_count} old backups")

    def get_rollback_history(self, limit: int = 10) -> list[BackupMetadata]:
        """
        Get recent rollback history.

        Args:
            limit: Maximum number of entries

        Returns:
            List of BackupMetadata
        """
        backups = self.list_backups()
        return backups[:limit]

    def verify_backup_integrity(self, backup_id: str) -> bool:
        """
        Verify a backup's integrity.

        Args:
            backup_id: Backup to verify

        Returns:
            True if backup is valid
        """
        metadata = self.load_metadata(backup_id)
        if not metadata:
            return False

        # Check if backup files exist
        for original_file in metadata.original_files:
            backup_pattern = f"*{Path(original_file).stem}*.java"
            backups = list(self.backup_dir.glob(backup_pattern))
            if not backups:
                return False

        return True
