"""
Git Integration Wrapper for GenEC.

Provides safe Git operations for refactoring application including:
- Branch creation/management
- Atomic commits
- Rollback support
- Conflict detection
"""

from dataclasses import dataclass
from pathlib import Path

from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class GitStatus:
    """Git repository status."""

    is_repo: bool
    current_branch: str
    has_uncommitted_changes: bool
    is_clean: bool


class GitWrapper:
    """
    Wrapper for Git operations to support safe refactoring application.

    Uses GitPython library for robust Git integration.
    """

    def __init__(self, repo_path: str):
        """
        Initialize Git wrapper.

        Args:
            repo_path: Path to Git repository root
        """
        self.repo_path = Path(repo_path)
        self.logger = get_logger(self.__class__.__name__)

        # Try to import GitPython
        try:
            import git

            self.git = git
            self.repo = git.Repo(repo_path)
        except ImportError:
            self.logger.warning("GitPython not installed. Git features disabled.")
            self.git = None
            self.repo = None
        except git.exc.InvalidGitRepositoryError:
            self.logger.warning(f"{repo_path} is not a Git repository. Git features disabled.")
            self.git = None
            self.repo = None

    def is_available(self) -> bool:
        """Check if Git integration is available."""
        return self.git is not None and self.repo is not None

    def get_status(self) -> GitStatus:
        """
        Get current Git repository status.

        Returns:
            GitStatus with repository information
        """
        if not self.is_available():
            return GitStatus(
                is_repo=False, current_branch="", has_uncommitted_changes=False, is_clean=True
            )

        return GitStatus(
            is_repo=True,
            current_branch=self.repo.active_branch.name,
            has_uncommitted_changes=self.repo.is_dirty(),
            is_clean=not self.repo.is_dirty(),
        )

    def create_branch(self, branch_name: str, from_branch: str | None = None) -> bool:
        """
        Create a new branch.

        Args:
            branch_name: Name of new branch
            from_branch: Branch to create from (default: current)

        Returns:
            True if successful
        """
        if not self.is_available():
            self.logger.warning("Git not available, cannot create branch")
            return False

        try:
            # Check if branch already exists
            if branch_name in self.repo.heads:
                self.logger.info(f"Branch {branch_name} already exists, checking out")
                self.repo.heads[branch_name].checkout()
                return True

            # Create new branch
            if from_branch:
                base = self.repo.heads[from_branch]
            else:
                base = self.repo.active_branch

            new_branch = self.repo.create_head(branch_name, base)
            new_branch.checkout()

            self.logger.info(f"Created and checked out branch: {branch_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to create branch {branch_name}: {e}")
            return False

    def checkout_branch(self, branch_name: str) -> bool:
        """
        Checkout an existing branch.

        Args:
            branch_name: Branch to checkout

        Returns:
            True if successful
        """
        if not self.is_available():
            return False

        try:
            self.repo.heads[branch_name].checkout()
            self.logger.info(f"Checked out branch: {branch_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to checkout {branch_name}: {e}")
            return False

    def create_commit(
        self,
        message: str,
        files: list[str] | None = None,
        author_name: str | None = None,
        author_email: str | None = None,
    ) -> str | None:
        """
        Create a Git commit.

        Args:
            message: Commit message
            files: Files to add (default: all modified)
            author_name: Optional author name
            author_email: Optional author email

        Returns:
            Commit hash if successful, None otherwise
        """
        if not self.is_available():
            self.logger.warning("Git not available, cannot create commit")
            return None

        try:
            # Add files
            if files:
                self.repo.index.add(files)
            else:
                self.repo.git.add(A=True)  # Add all

            # Create commit
            if author_name and author_email:
                actor = self.git.Actor(author_name, author_email)
                commit = self.repo.index.commit(message, author=actor, committer=actor)
            else:
                commit = self.repo.index.commit(message)

            commit_hash = commit.hexsha[:7]
            self.logger.info(f"Created commit {commit_hash}: {message.split(chr(10))[0]}")
            return commit_hash

        except Exception as e:
            self.logger.error(f"Failed to create commit: {e}")
            return None

    def revert_commit(self, commit_hash: str) -> bool:
        """
        Revert a specific commit.

        Args:
            commit_hash: Commit to revert

        Returns:
            True if successful
        """
        if not self.is_available():
            return False

        try:
            self.repo.git.revert(commit_hash, no_edit=True)
            self.logger.info(f"Reverted commit: {commit_hash}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to revert {commit_hash}: {e}")
            return False

    def get_file_hash(self, file_path: str) -> str | None:
        """
        Get Git hash (blob ID) of a file at HEAD.

        Args:
            file_path: Path to file (relative to repo root)

        Returns:
            Git blob hash or None
        """
        if not self.is_available():
            return None

        try:
            # Get file contents at HEAD
            blob = self.repo.head.commit.tree / file_path
            return blob.hexsha
        except Exception:
            return None

    def has_conflicts(self, file_path: str) -> bool:
        """
        Check if file has been modified since HEAD.

        Args:
            file_path: Path to file

        Returns:
            True if file differs from HEAD
        """
        if not self.is_available():
            return False

        try:
            # Check if file is in modified files
            return file_path in [item.a_path for item in self.repo.index.diff(None)]
        except Exception:
            return False

    def get_diff(self, file_path: str, staged: bool = False) -> str | None:
        """
        Get diff for a specific file.

        Args:
            file_path: Path to file
            staged: Get staged diff (default: working tree)

        Returns:
            Unified diff string or None
        """
        if not self.is_available():
            return None

        try:
            if staged:
                diff = self.repo.git.diff("--cached", file_path)
            else:
                diff = self.repo.git.diff(file_path)
            return diff
        except Exception as e:
            self.logger.warning(f"Could not get diff for {file_path}: {e}")
            return None

    def delete_branch(self, branch_name: str, force: bool = False) -> bool:
        """
        Delete a branch.

        Args:
            branch_name: Branch to delete
            force: Force deletion even if unmerged

        Returns:
            True if successful
        """
        if not self.is_available():
            return False

        try:
            self.repo.delete_head(branch_name, force=force)
            self.logger.info(f"Deleted branch: {branch_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete branch {branch_name}: {e}")
            return False

    def get_current_commit(self) -> str | None:
        """Get current commit hash."""
        if not self.is_available():
            return None
        return self.repo.head.commit.hexsha[:7]

    def get_changed_files(self) -> list[str]:
        """Get list of changed files in working tree."""
        if not self.is_available():
            return []

        changed = []
        for item in self.repo.index.diff(None):
            changed.append(item.a_path)
        for item in self.repo.untracked_files:
            changed.append(item)
        return changed


def generate_commit_message(suggestion, original_class_name: str, version: str = "1.0") -> str:
    """
    Generate descriptive commit message for a refactoring.

    Args:
        suggestion: RefactoringSuggestion object
        original_class_name: Name of original class
        version: GenEC version

    Returns:
        Formatted commit message
    """
    # Extract methods from cluster
    methods = [m for m in suggestion.cluster.member_names if "(" in m]
    fields = [f for f in suggestion.cluster.member_names if "(" not in f]

    # Build message
    lines = [
        f"refactor: Extract {suggestion.proposed_class_name} from {original_class_name}",
        "",
        "Extracted members:",
    ]

    if methods:
        lines.append("Methods:")
        for method in methods[:5]:  # Limit to 5
            lines.append(f"  - {method}")
        if len(methods) > 5:
            lines.append(f"  ... and {len(methods) - 5} more")

    if fields:
        lines.append("Fields:")
        for field in fields[:5]:
            lines.append(f"  - {field}")
        if len(fields) > 5:
            lines.append(f"  ... and {len(fields) - 5} more")

    lines.extend(
        [
            "",
            (
                f"Rationale: {suggestion.rationale[:200]}..."
                if len(suggestion.rationale) > 200
                else f"Rationale: {suggestion.rationale}"
            ),
            "",
            f"Cluster ID: {suggestion.cluster_id}",
        ]
    )

    if hasattr(suggestion, "confidence_score") and suggestion.confidence_score:
        lines.append(f"Confidence: {suggestion.confidence_score:.2f}")

    lines.extend(["", f"Generated by GenEC v{version}"])

    return "\n".join(lines)
