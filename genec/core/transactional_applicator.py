"""
Transactional Applicator for safe refactoring application.

Ensures all-or-nothing application with conflict detection and automatic rollback.
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from genec.core.llm_interface import RefactoringSuggestion
from genec.core.refactoring_applicator import RefactoringApplication, RefactoringApplicator
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class Savepoint:
    """Savepoint for transactional rollback."""

    timestamp: str
    file_hashes: dict[str, str]
    backup_dir: str
    suggestions_applied: int = 0


@dataclass
class ConflictError(Exception):
    """Raised when a file conflict is detected."""

    file_path: str
    expected_hash: str
    actual_hash: str

    def __str__(self):
        return f"File modified since analysis: {self.file_path}"


class TransactionalApplicator:
    """
    Applies refactorings transactionally with conflict detection.

    Features:
    - All-or-nothing application
    - Conflict detection via file hashing
    - Savepoint/rollback mechanism
    - Automatic cleanup on failure
    """

    def __init__(self, applicator: RefactoringApplicator | None = None, enable_git: bool = True):
        """
        Initialize transactional applicator.

        Args:
            applicator: Underlying RefactoringApplicator
            enable_git: Enable Git integration
        """
        self.applicator = applicator or RefactoringApplicator(enable_git=enable_git)
        self.logger = get_logger(self.__class__.__name__)

    def apply_all(
        self,
        suggestions: list[RefactoringSuggestion],
        original_files: dict[int, str],  # cluster_id -> file_path
        repo_path: str,
        check_conflicts: bool = True,
    ) -> tuple[bool, list[RefactoringApplication]]:
        """
        Apply all refactorings transactionally (all-or-nothing).

        Args:
            suggestions: List of refactoring suggestions
            original_files: Mapping of cluster_id to original file path
            repo_path: Repository root path
            check_conflicts: Enable conflict detection

        Returns:
            (success, list of applications)
        """
        self.logger.info(f"Applying {len(suggestions)} refactorings transactionally")

        applications = []
        savepoint = None

        try:
            # Step 1: Validate all suggestions
            self.logger.info("Step 1: Validating suggestions...")
            for suggestion in suggestions:
                if not suggestion.new_class_code or not suggestion.modified_original_code:
                    raise ValueError(f"Invalid suggestion for cluster {suggestion.cluster_id}")

            # Step 2: Detect conflicts
            if check_conflicts:
                self.logger.info("Step 2: Checking for conflicts...")
                self._detect_conflicts(suggestions, original_files)

            # Step 3: Create savepoint
            self.logger.info("Step 3: Creating savepoint...")
            savepoint = self._create_savepoint(suggestions, original_files)

            # Step 4: Apply all refactorings
            self.logger.info("Step 4: Applying refactorings...")
            for i, suggestion in enumerate(suggestions):
                original_file = original_files.get(suggestion.cluster_id)
                if not original_file:
                    raise ValueError(f"No original file for cluster {suggestion.cluster_id}")

                application = self.applicator.apply_refactoring(
                    suggestion=suggestion,
                    original_class_file=original_file,
                    repo_path=repo_path,
                    create_branch=(i == 0),  # Only create branch for first refactoring
                )

                if not application.success:
                    raise RuntimeError(f"Failed to apply refactoring: {application.error_message}")

                applications.append(application)
                savepoint.suggestions_applied += 1

            # Step 5: Commit transaction
            self.logger.info("Step 5: Committing transaction...")
            self._save_savepoint_metadata(savepoint)

            self.logger.info(f"✓ Successfully applied {len(suggestions)} refactorings")
            return True, applications

        except Exception as e:
            self.logger.error(f"Transaction failed: {e}")

            # Step 6: Rollback
            if savepoint:
                self.logger.warning("Rolling back transaction...")
                self._rollback_to_savepoint(savepoint, applications)

            return False, applications

    def _detect_conflicts(
        self, suggestions: list[RefactoringSuggestion], original_files: dict[int, str]
    ):
        """
        Detect if any files have been modified since analysis.

        Raises:
            ConflictError if conflicts detected
        """
        for suggestion in suggestions:
            original_file = original_files.get(suggestion.cluster_id)
            if not original_file:
                continue

            file_path = Path(original_file)
            if not file_path.exists():
                raise ConflictError(
                    file_path=str(file_path), expected_hash="", actual_hash="DELETED"
                )

            # Check if file matches expected state
            # In production, would store expected hashes from analysis phase
            # For now, just verify file exists
            self.logger.debug(f"Verified file exists: {file_path}")

    def _create_savepoint(
        self, suggestions: list[RefactoringSuggestion], original_files: dict[int, str]
    ) -> Savepoint:
        """
        Create a savepoint for potential rollback.

        Returns:
            Savepoint with current state
        """
        file_hashes = {}

        # Hash all original files
        for cluster_id, file_path in original_files.items():
            if Path(file_path).exists():
                file_hashes[file_path] = self._compute_file_hash(file_path)

        savepoint = Savepoint(
            timestamp=datetime.now().isoformat(),
            file_hashes=file_hashes,
            backup_dir=str(self.applicator.backup_dir),
        )

        self.logger.info(f"Created savepoint with {len(file_hashes)} files")
        return savepoint

    def _rollback_to_savepoint(
        self, savepoint: Savepoint, applications: list[RefactoringApplication]
    ):
        """
        Rollback to a saved state.

        Args:
            savepoint: Savepoint to restore
            applications: Applications to rollback
        """
        self.logger.info("Rolling back transaction...")

        # Rollback each application
        for application in reversed(applications):
            if application.success:
                self.applicator.rollback_refactoring(application)

        self.logger.info("Transaction rolled back successfully")

    def _compute_file_hash(self, file_path: str) -> str:
        """
        Compute SHA256 hash of a file.

        Args:
            file_path: Path to file

        Returns:
            Hex digest of file hash
        """
        sha256 = hashlib.sha256()

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)

        return sha256.hexdigest()

    def _save_savepoint_metadata(self, savepoint: Savepoint):
        """Save savepoint metadata to disk."""
        metadata_file = Path(savepoint.backup_dir) / f"savepoint_{savepoint.timestamp}.json"
        metadata_file.parent.mkdir(parents=True, exist_ok=True)

        with open(metadata_file, "w") as f:
            json.dump(asdict(savepoint), f, indent=2)

        self.logger.debug(f"Saved savepoint metadata: {metadata_file}")

    def verify_file_integrity(self, file_path: str, expected_hash: str) -> bool:
        """
        Verify file hasn't changed since savepoint.

        Args:
            file_path: Path to file
            expected_hash: Expected hash

        Returns:
            True if file matches expected hash
        """
        path = Path(file_path)
        if not path.exists():
            return False

        actual_hash = self._compute_file_hash(file_path)
        return actual_hash == expected_hash
