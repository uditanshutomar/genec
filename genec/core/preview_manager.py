"""
Preview and Dry-Run Manager for GenEC.

Provides preview capabilities before applying refactorings:
- Dry-run mode
- Unified diff generation
- Change statistics
- Preview visualization
"""

import difflib
from dataclasses import dataclass
from pathlib import Path

from genec.core.llm_interface import RefactoringSuggestion
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class ChangeStatistics:
    """Statistics about proposed changes."""

    files_created: int
    files_modified: int
    files_deleted: int
    lines_added: int
    lines_removed: int
    lines_modified: int
    total_lines_before: int
    total_lines_after: int


@dataclass
class FilePreview:
    """Preview of changes to a single file."""

    file_path: str
    action: str  # "create", "modify", "delete"
    unified_diff: str
    before_content: str | None = None
    after_content: str | None = None
    lines_added: int = 0
    lines_removed: int = 0


@dataclass
class RefactoringPreview:
    """Complete preview of a refactoring."""

    refactoring_name: str
    cluster_id: int
    files: list[FilePreview]
    statistics: ChangeStatistics
    can_apply: bool = True
    warnings: list[str] = None


class PreviewManager:
    """
    Manages preview and dry-run operations.

    Features:
    - Generate unified diffs
    - Calculate change statistics
    - Preview before application
    - Validate changes
    """

    def __init__(self):
        """Initialize preview manager."""
        self.logger = get_logger(self.__class__.__name__)

    def preview_refactoring(
        self, suggestion: RefactoringSuggestion, original_file: str, repo_path: str
    ) -> RefactoringPreview:
        """
        Generate preview for a refactoring.

        Args:
            suggestion: Refactoring suggestion
            original_file: Path to original file
            repo_path: Repository root

        Returns:
            RefactoringPreview with all changes
        """
        files = []
        warnings = []

        # Preview original file modification
        original_path = Path(original_file)
        if original_path.exists():
            before_content = original_path.read_text()
            after_content = suggestion.modified_original_code

            modified_preview = self._preview_file_modification(
                str(original_path), before_content, after_content
            )
            files.append(modified_preview)
        else:
            warnings.append(f"Original file not found: {original_file}")

        # Preview new file creation
        new_file_path = self._compute_new_file_path(original_path, suggestion.proposed_class_name)

        if new_file_path.exists():
            warnings.append(f"New file already exists: {new_file_path}")

        created_preview = self._preview_file_creation(str(new_file_path), suggestion.new_class_code)
        files.append(created_preview)

        # Calculate statistics
        statistics = self._calculate_statistics(files)

        return RefactoringPreview(
            refactoring_name=suggestion.proposed_class_name,
            cluster_id=suggestion.cluster_id,
            files=files,
            statistics=statistics,
            can_apply=len(warnings) == 0,
            warnings=warnings if warnings else None,
        )

    def preview_multiple(
        self,
        suggestions: list[RefactoringSuggestion],
        original_files: dict[int, str],
        repo_path: str,
    ) -> list[RefactoringPreview]:
        """
        Preview multiple refactorings.

        Args:
            suggestions: List of suggestions
            original_files: Mapping of cluster_id to file path
            repo_path: Repository root

        Returns:
            List of RefactoringPreview
        """
        previews = []

        for suggestion in suggestions:
            original_file = original_files.get(suggestion.cluster_id)
            if original_file:
                preview = self.preview_refactoring(suggestion, original_file, repo_path)
                previews.append(preview)

        return previews

    def _preview_file_modification(self, file_path: str, before: str, after: str) -> FilePreview:
        """Generate preview for file modification."""
        # Generate unified diff
        diff = self._generate_unified_diff(
            before, after, fromfile=f"a/{file_path}", tofile=f"b/{file_path}"
        )

        # Count changes
        lines_added, lines_removed = self._count_diff_changes(diff)

        return FilePreview(
            file_path=file_path,
            action="modify",
            unified_diff=diff,
            before_content=before,
            after_content=after,
            lines_added=lines_added,
            lines_removed=lines_removed,
        )

    def _preview_file_creation(self, file_path: str, content: str) -> FilePreview:
        """Generate preview for file creation."""
        # Diff shows all lines as added
        diff = self._generate_unified_diff(
            "", content, fromfile="/dev/null", tofile=f"b/{file_path}"
        )

        lines_added = content.count("\n") + 1

        return FilePreview(
            file_path=file_path,
            action="create",
            unified_diff=diff,
            before_content=None,
            after_content=content,
            lines_added=lines_added,
            lines_removed=0,
        )

    def _generate_unified_diff(
        self,
        before: str,
        after: str,
        fromfile: str = "before",
        tofile: str = "after",
        lineterm: str = "",
    ) -> str:
        """
        Generate unified diff between two contents.

        Args:
            before: Original content
            after: Modified content
            fromfile: Source file label
            tofile: Destination file label
            lineterm: Line terminator

        Returns:
            Unified diff string
        """
        before_lines = before.splitlines(keepends=True)
        after_lines = after.splitlines(keepends=True)

        diff = difflib.unified_diff(
            before_lines, after_lines, fromfile=fromfile, tofile=tofile, lineterm=lineterm
        )

        return "".join(diff)

    def _count_diff_changes(self, diff: str) -> tuple[int, int]:
        """
        Count added and removed lines in diff.

        Returns:
            (lines_added, lines_removed)
        """
        lines_added = 0
        lines_removed = 0

        for line in diff.split("\n"):
            if line.startswith("+") and not line.startswith("+++"):
                lines_added += 1
            elif line.startswith("-") and not line.startswith("---"):
                lines_removed += 1

        return lines_added, lines_removed

    def _calculate_statistics(self, files: list[FilePreview]) -> ChangeStatistics:
        """Calculate overall statistics from file previews."""
        files_created = sum(1 for f in files if f.action == "create")
        files_modified = sum(1 for f in files if f.action == "modify")
        files_deleted = sum(1 for f in files if f.action == "delete")

        lines_added = sum(f.lines_added for f in files)
        lines_removed = sum(f.lines_removed for f in files)
        lines_modified = min(lines_added, lines_removed)

        # Calculate total lines before/after
        total_before = 0
        total_after = 0

        for f in files:
            if f.before_content:
                total_before += f.before_content.count("\n") + 1
            if f.after_content:
                total_after += f.after_content.count("\n") + 1

        return ChangeStatistics(
            files_created=files_created,
            files_modified=files_modified,
            files_deleted=files_deleted,
            lines_added=lines_added,
            lines_removed=lines_removed,
            lines_modified=lines_modified,
            total_lines_before=total_before,
            total_lines_after=total_after,
        )

    def _compute_new_file_path(self, original_path: Path, new_class_name: str) -> Path:
        """Compute path for new extracted class."""
        return original_path.parent / f"{new_class_name}.java"

    def format_preview(self, preview: RefactoringPreview, show_diff: bool = True) -> str:
        """
        Format preview as human-readable string.

        Args:
            preview: RefactoringPreview to format
            show_diff: Include unified diffs

        Returns:
            Formatted preview string
        """
        lines = []
        lines.append("=" * 80)
        lines.append(f"PREVIEW: Extract {preview.refactoring_name}")
        lines.append("=" * 80)

        # Statistics
        stats = preview.statistics
        lines.append("\nChange Statistics:")
        lines.append(f"  Files created:  {stats.files_created}")
        lines.append(f"  Files modified: {stats.files_modified}")
        lines.append(f"  Files deleted:  {stats.files_deleted}")
        lines.append(f"  Lines added:    +{stats.lines_added}")
        lines.append(f"  Lines removed:  -{stats.lines_removed}")
        lines.append(f"  Lines modified: ~{stats.lines_modified}")
        lines.append(f"  Total before:   {stats.total_lines_before}")
        lines.append(f"  Total after:    {stats.total_lines_after}")

        # Warnings
        if preview.warnings:
            lines.append("\n⚠️  Warnings:")
            for warning in preview.warnings:
                lines.append(f"  - {warning}")

        # File changes
        lines.append("\nFile Changes:")
        for file_preview in preview.files:
            action_emoji = "📝" if file_preview.action == "modify" else "📄"
            lines.append(
                f"\n{action_emoji} {file_preview.action.upper()}: {file_preview.file_path}"
            )
            lines.append(f"   +{file_preview.lines_added} -{file_preview.lines_removed} lines")

            if show_diff and file_preview.unified_diff:
                lines.append("\n" + file_preview.unified_diff)

        # Can apply
        lines.append("\n" + "=" * 80)
        if preview.can_apply:
            lines.append("✅ Ready to apply")
        else:
            lines.append("❌ Cannot apply (see warnings)")
        lines.append("=" * 80)

        return "\n".join(lines)

    def format_summary(self, previews: list[RefactoringPreview]) -> str:
        """
        Format summary of multiple previews.

        Args:
            previews: List of previews

        Returns:
            Summary string
        """
        lines = []
        lines.append("=" * 80)
        lines.append(f"REFACTORING PREVIEW SUMMARY ({len(previews)} refactorings)")
        lines.append("=" * 80)

        total_created = sum(p.statistics.files_created for p in previews)
        total_modified = sum(p.statistics.files_modified for p in previews)
        total_added = sum(p.statistics.lines_added for p in previews)
        total_removed = sum(p.statistics.lines_removed for p in previews)

        lines.append("\nTotal Impact:")
        lines.append(f"  Files created:  {total_created}")
        lines.append(f"  Files modified: {total_modified}")
        lines.append(f"  Lines added:    +{total_added}")
        lines.append(f"  Lines removed:  -{total_removed}")

        lines.append("\nRefactorings:")
        for i, preview in enumerate(previews, 1):
            status = "✅" if preview.can_apply else "❌"
            lines.append(
                f"  {i}. {status} {preview.refactoring_name} "
                f"(+{preview.statistics.lines_added} -{preview.statistics.lines_removed})"
            )

        can_apply_all = all(p.can_apply for p in previews)
        lines.append("\n" + "=" * 80)
        if can_apply_all:
            lines.append("✅ All refactorings ready to apply")
        else:
            failed = sum(1 for p in previews if not p.can_apply)
            lines.append(f"⚠️  {failed} refactoring(s) cannot be applied")
        lines.append("=" * 80)

        return "\n".join(lines)
