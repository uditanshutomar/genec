"""Evolutionary coupling miner using Git history."""

import concurrent.futures
import hashlib
import multiprocessing
import os
import pickle
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import git
import numpy as np
from git import GitCommandError, Repo

from genec.core.hybrid_dependency_analyzer import HybridDependencyAnalyzer
from genec.parsers.java_parser import JavaParser
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class EvolutionaryData:
    """Evolutionary coupling data extracted from Git history.

    Note: All method tracking uses full method SIGNATURES (e.g., "process(int,String)")
    rather than simple names, to support precise overload handling.
    """

    class_file: str
    method_names: set[str] = field(default_factory=set)  # Set of method SIGNATURES
    method_commits: dict[str, int] = field(default_factory=dict)  # signature -> commit count
    cochange_matrix: dict[tuple[str, str], int] = field(
        default_factory=dict
    )  # (sig1, sig2) -> count
    coupling_strengths: dict[tuple[str, str], float] = field(
        default_factory=dict
    )  # (sig1, sig2) -> strength
    total_commits: int = 0


def process_commit_worker(
    repo_path: str, commit_sha: str, file_path: str, max_changeset_size: int
) -> set[str]:
    """Worker function to process a single commit in a separate process."""
    try:
        # Initialize a lightweight miner for this worker
        miner = EvolutionaryMiner(max_changeset_size=max_changeset_size)

        # Re-open repo in this process
        repo = Repo(repo_path)
        commit = repo.commit(commit_sha)

        return miner._extract_changed_methods(repo, commit, file_path)
    except Exception:
        # Return empty set on failure to avoid crashing the pool
        return set()


class EvolutionaryMiner:
    """Mines evolutionary coupling from Git commit history."""

    def __init__(
        self,
        cache_dir: str | None = None,
        min_coupling_threshold: float = 0.3,
        max_changeset_size: int = 30,
        min_revisions: int = 5,
        prefer_spoon: bool = False,
    ):
        """
        Initialize the evolutionary miner.

        Args:
            cache_dir: Directory for caching mining results
            min_coupling_threshold: Minimum coupling threshold (default 0.3 like Code-Maat)
            max_changeset_size: Maximum changeset size to avoid refactoring noise (default 30)
            min_revisions: Minimum revisions required for method (default 5)
            prefer_spoon: Whether to prefer Spoon (JVM) over lightweight parser (default: False)
        """
        # Use hybrid analyzer (Spoon + JavaParser fallback)
        # For mining, we prefer the lightweight parser (JavaParser/Regex) because spawning
        # a JVM for every commit is too slow and resource-intensive.
        self.dependency_analyzer = HybridDependencyAnalyzer(prefer_spoon=prefer_spoon)
        # Keep JavaParser for legacy fallback in simple parsing
        self.parser = JavaParser()
        self.logger = get_logger(self.__class__.__name__)
        self.cache_dir = Path(cache_dir) if cache_dir else None

        # Code-Maat-style filtering parameters
        self.min_coupling_threshold = min_coupling_threshold
        self.max_changeset_size = max_changeset_size
        self.min_revisions = min_revisions

        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Cache for method signatures per commit
        self.method_cache: dict[str, dict[str, tuple[int, int]]] = {}

    def mine_method_cochanges(
        self,
        class_file: str,
        repo_path: str,
        window_months: int = 12,
        min_commits: int = 2,
        show_metrics: bool = True,
        max_workers: int | None = None,
    ) -> EvolutionaryData:
        """
        Mine method co-changes from Git history.

        Args:
            class_file: Path to class file (relative to repo root)
            repo_path: Path to Git repository
            window_months: How many months back to look
            min_commits: Minimum commits for a method to be considered
            show_metrics: If True, automatically print parser metrics (default: True)
            max_workers: Number of parallel workers (default: CPU count)

        Returns:
            EvolutionaryData object with coupling information
        """
        self.logger.info(f"Mining evolutionary coupling for {class_file}")
        normalized_class_file = Path(class_file).as_posix() if class_file else class_file

        try:
            repo = Repo(repo_path)

            # Check for git lock file to prevent conflicts with other git operations
            git_lock_file = Path(repo_path) / ".git" / "index.lock"
            if git_lock_file.exists():
                self.logger.warning(
                    f"Git lock file detected: {git_lock_file}. "
                    "Another git operation may be in progress. "
                    "Waiting briefly or consider removing stale lock."
                )
                # Wait briefly in case it's a transient lock
                import time

                time.sleep(1)
                if git_lock_file.exists():
                    self.logger.error(
                        "Git lock file still present. Skipping mining to avoid conflicts."
                    )
                    return EvolutionaryData(class_file=normalized_class_file)

        except Exception as e:
            self.logger.error(f"Failed to open repository {repo_path}: {e}")
            return EvolutionaryData(class_file=normalized_class_file)

        repo_signature = self._get_repo_signature(repo, normalized_class_file)

        # Check cache
        cache_key = self._get_cache_key(
            normalized_class_file, window_months, min_commits, repo_signature
        )
        if self.cache_dir and self._is_cache_valid(cache_key):
            cached_data = self._load_from_cache(cache_key)
            if cached_data:
                self.logger.info("Using cached evolutionary data")
                return cached_data

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=window_months * 30)

        # Get commits affecting the file
        commits = self._get_file_commits(repo, normalized_class_file, start_date, end_date)

        if not commits:
            self.logger.warning(f"No commits found for {normalized_class_file} in the time window")
            return EvolutionaryData(class_file=normalized_class_file)

        self.logger.info(f"Found {len(commits)} commits affecting {normalized_class_file}")

        # Track method changes per commit
        evo_data = EvolutionaryData(class_file=normalized_class_file, total_commits=len(commits))

        # Process commits in parallel
        if max_workers is None:
            max_workers = multiprocessing.cpu_count()

        self.logger.info(f"Processing commits with {max_workers} workers...")

        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Prepare arguments for each commit
            future_to_commit = {
                executor.submit(
                    process_commit_worker,
                    repo_path,
                    commit.hexsha,
                    normalized_class_file,
                    self.max_changeset_size,
                ): commit
                for commit in commits
            }

            for future in concurrent.futures.as_completed(future_to_commit):
                try:
                    changed_methods = future.result()

                    # Update method commit counts
                    for method in changed_methods:
                        evo_data.method_names.add(method)
                        evo_data.method_commits[method] = evo_data.method_commits.get(method, 0) + 1

                    # Update co-change matrix
                    for m1 in changed_methods:
                        for m2 in changed_methods:
                            if m1 < m2:  # Only store once (ordered pair)
                                key = (m1, m2)
                                evo_data.cochange_matrix[key] = (
                                    evo_data.cochange_matrix.get(key, 0) + 1
                                )

                except Exception as e:
                    self.logger.warning(f"Worker failed: {e}")

        # Filter methods by minimum commits (use min_revisions if not explicitly set)
        min_threshold = max(min_commits, self.min_revisions)
        filtered_methods = {
            m for m, count in evo_data.method_commits.items() if count >= min_threshold
        }
        evo_data.method_names = filtered_methods

        # Calculate coupling strengths
        self._calculate_coupling_strengths(evo_data)

        self.logger.info(
            f"Found {len(evo_data.method_names)} methods with >= {min_commits} commits"
        )

        # Cache the results
        if self.cache_dir:
            self._save_to_cache(cache_key, evo_data)

        # Auto-print parser metrics if enabled
        if show_metrics:
            self.print_analysis_metrics()

        return evo_data

    def _get_file_commits(
        self,
        repo: Repo,
        file_path: str,
        start_date: datetime,
        end_date: datetime,
        max_commits: int = 2000,  # Memory limit: stop after this many commits
    ) -> list[git.Commit]:
        """Get all commits affecting a file within a date range.

        Memory optimization: limits to max_commits to prevent OOM on large histories.
        """
        commits = []
        commit_count = 0

        try:
            # Get commits for the file with memory limit
            for commit in repo.iter_commits(paths=file_path, since=start_date.isoformat()):
                if commit.committed_datetime.replace(tzinfo=None) <= end_date:
                    commits.append(commit)
                    commit_count += 1

                    # Memory safeguard: warn and stop if too many commits
                    if commit_count >= max_commits:
                        self.logger.warning(
                            f"Large git history detected: {commit_count}+ commits. "
                            f"Limiting to {max_commits} most recent commits for memory efficiency. "
                            f"Consider reducing window_months in config."
                        )
                        break
        except GitCommandError as e:
            error_str = str(e).lower()
            # Check if this is a transient/retryable error
            if any(keyword in error_str for keyword in ["lock", "timeout", "busy", "temporary"]):
                self.logger.warning(f"Transient git error, retrying: {e}")
                import time

                for retry in range(3):
                    try:
                        time.sleep(2**retry)  # Exponential backoff: 1s, 2s, 4s
                        # Retry the git operation
                        for commit in repo.iter_commits(
                            paths=file_path, since=start_date.isoformat()
                        ):
                            if commit.committed_datetime.replace(tzinfo=None) <= end_date:
                                if commit not in commits:  # Avoid duplicates
                                    commits.append(commit)
                        self.logger.info(f"Git retry {retry + 1} succeeded")
                        break
                    except GitCommandError as retry_error:
                        if retry == 2:  # Last retry
                            self.logger.error(f"Git retry failed after 3 attempts: {retry_error}")
            else:
                self.logger.error(f"Git command error: {e}")

        return commits

    def _extract_changed_methods(self, repo: Repo, commit: git.Commit, file_path: str) -> set[str]:
        """
        Extract methods that changed in a specific commit.

        Args:
            repo: Git repository
            commit: Commit to analyze
            file_path: Path to file

        Returns:
            Set of changed method signatures
        """
        changed_methods = set()

        try:
            # Get the diff for this commit
            if not commit.parents:
                # Initial commit - consider all methods as changed
                try:
                    file_content = (commit.tree / file_path).data_stream.read().decode("utf-8")
                    methods = self._extract_methods_from_content(file_content, commit.hexsha)
                    return set(methods)
                except:
                    return set()

            parent = commit.parents[0]

            try:
                # Get file contents before and after
                old_content = (parent.tree / file_path).data_stream.read().decode("utf-8")
                new_content = (commit.tree / file_path).data_stream.read().decode("utf-8")

                # Get diff with porcelain format for better machine readability
                diff = repo.git.diff(
                    parent.hexsha,
                    commit.hexsha,
                    file_path,
                    unified=0,
                    histogram=True,  # Better function detection algorithm
                )

                # Extract changed line ranges
                changed_lines = self._extract_changed_lines(diff)

                # Get methods in both versions with caching
                old_methods = self._extract_methods_with_lines(old_content, parent.hexsha)
                new_methods = self._extract_methods_with_lines(new_content, commit.hexsha)

                # Check which methods overlap with changed lines
                for method_sig, (start, end) in new_methods.items():
                    for changed_start, changed_end in changed_lines:
                        if not (end < changed_start or start > changed_end):
                            # Method overlaps with changed lines
                            changed_methods.add(method_sig)
                            break

                # Filter large changesets to reduce refactoring noise
                if len(changed_methods) > self.max_changeset_size:
                    self.logger.debug(
                        f"Skipping large changeset: {len(changed_methods)} methods "
                        f"(max: {self.max_changeset_size})"
                    )
                    return set()

            except Exception as e:
                self.logger.debug(f"Error processing diff: {e}")

        except Exception as e:
            self.logger.debug(f"Error extracting changed methods: {e}")

        return changed_methods

    def _extract_changed_lines(self, diff: str) -> list[tuple[int, int]]:
        """
        Extract changed line ranges from unified diff.

        Returns:
            List of (start_line, end_line) tuples
        """
        changed_ranges = []

        # Parse diff hunks: @@ -start,count +start,count @@
        hunk_pattern = r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@"

        for match in re.finditer(hunk_pattern, diff):
            start = int(match.group(1))
            count = int(match.group(2)) if match.group(2) else 1
            end = start + count - 1
            changed_ranges.append((start, end))

        return changed_ranges

    def _extract_methods_from_content(
        self, content: str, commit_sha: str | None = None
    ) -> list[str]:
        """
        Extract method signatures from Java source content using Spoon.

        Args:
            content: Java source code content
            commit_sha: Optional commit SHA for caching

        Returns:
            List of method signatures (e.g., ["process(int,String)", "validate()"])
        """
        import tempfile

        methods = []

        try:
            # Write content to temporary file for Spoon analysis
            with tempfile.NamedTemporaryFile(mode="w", suffix=".java", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                # Use hybrid analyzer to parse the file
                result = self.dependency_analyzer.analyze_class(tmp_path)
                if result:
                    # Extract method signatures
                    for method in result.methods:
                        methods.append(method.signature)
                    # Include constructor signatures
                    for ctor in result.constructors:
                        methods.append(ctor.signature)
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        except Exception as e:
            self.logger.debug(f"Failed to extract methods with Spoon, using fallback: {e}")
            # Fallback to simple regex extraction
            methods = self._extract_methods_simple(content)

        return methods

    def _extract_methods_simple(self, content: str) -> list[str]:
        """Simple regex-based method extraction as fallback."""
        methods = []
        lines = content.split("\n")

        # Match method declarations - now handles generic return types
        # Pattern: modifiers? generic_params? return_type<generics>? method_name(params)
        method_pattern = r"^\s*(?:public|private|protected)?\s*(?:static)?\s*(?:final)?\s*(?:<[^>]+>)?\s*([\w.<>]+(?:<[^>]+>)?)\s+(\w+)\s*\(([^)]*)\)"

        for line in lines:
            match = re.search(method_pattern, line)
            if match:
                return_type = match.group(1)
                method_name = match.group(2)
                params = match.group(3).strip()

                # Skip class declarations and other non-methods
                if return_type in ["class", "interface", "enum", "record"]:
                    continue

                # Build simple signature
                if params:
                    param_types = self._extract_param_types(params)
                    signature = f"{method_name}({','.join(param_types)})"
                else:
                    signature = f"{method_name}()"

                methods.append(signature)

        return methods

    def _extract_param_types(self, params_str: str) -> list[str]:
        """
        Extract parameter types from parameter list string.

        Handles cases like:
        - "int x" -> "int"
        - "String name" -> "String"
        - "List<String> items" -> "List<String>"
        - "Map<String, Integer> map" -> "Map<String,Integer>"
        - "int x, String y" -> ["int", "String"]

        Args:
            params_str: Parameter list string (e.g., "int x, String y")

        Returns:
            List of parameter type names (with generics preserved, spaces removed)
        """
        if not params_str:
            return []

        param_types = []

        # Split by comma, but we need to be careful about commas inside generics
        # Use a simple state machine to split correctly
        params = self._split_params_preserving_generics(params_str)

        for param in params:
            param = param.strip()
            if not param:
                continue

            # Extract type from "Type<Generic> paramName" or "Type paramName"
            # Strategy: Find the last identifier (param name) and everything before it is the type

            # Handle generic types with nested brackets
            # Count brackets to find where the type ends
            param_type = self._extract_type_from_param(param)
            if param_type:
                # Remove spaces from generic types (List<String> -> List<String> is ok, but Map<String, Integer> -> Map<String,Integer>)
                param_type = self._normalize_generic_type(param_type)
                param_types.append(param_type)

        return param_types

    def _split_params_preserving_generics(self, params_str: str) -> list[str]:
        """Split parameter string by comma, but preserve commas inside generics."""
        params = []
        current_param = []
        angle_bracket_depth = 0

        for char in params_str:
            if char == "<":
                angle_bracket_depth += 1
                current_param.append(char)
            elif char == ">":
                angle_bracket_depth -= 1
                current_param.append(char)
            elif char == "," and angle_bracket_depth == 0:
                # This is a parameter separator
                params.append("".join(current_param))
                current_param = []
            else:
                current_param.append(char)

        # Add the last parameter
        if current_param:
            params.append("".join(current_param))

        return params

    def _extract_type_from_param(self, param: str) -> str | None:
        """Extract type from a single parameter declaration like 'List<String> items' or 'int x'."""
        param = param.strip()

        # Remove leading annotations and modifiers
        param = re.sub(r"^\s*(@\w+\s+)*", "", param)
        param = re.sub(r"^\s*(final|var)\s+", "", param)

        # Strategy: Find the last word (parameter name) and take everything before it
        # But we need to handle generics carefully

        # Check for varargs
        is_varargs = False
        if "..." in param:
            is_varargs = True
            param = param.replace("...", "")

        # Find the last occurrence of a simple identifier (after any closing >)
        # Match: type (possibly with generics) followed by parameter name
        match = re.match(r"^([\w.<>[\]]+(?:<[^>]+>)?)\s+(\w+)$", param)
        if match:
            type_name = match.group(1)
            if is_varargs:
                type_name += "[]"
            return type_name

        # If no match, try a more flexible approach
        # Look for pattern: type_with_possible_generics whitespace param_name
        # Use bracket counting to find where type ends

        # Find the last identifier that's not inside brackets
        bracket_depth = 0
        last_space_idx = -1

        for i in range(len(param) - 1, -1, -1):
            char = param[i]
            if char in "<>":
                bracket_depth += 1 if char == ">" else -1
            elif char.isspace() and bracket_depth == 0:
                last_space_idx = i
                break

        if last_space_idx > 0:
            type_name = param[:last_space_idx].strip()
            if is_varargs:
                type_name += "[]"
            return type_name

        # No space found, might be just a type
        if is_varargs:
            param += "[]"
        return param

    def _normalize_generic_type(self, type_str: str) -> str:
        """Normalize generic type by removing spaces after commas in generics."""
        # Map<String, Integer> -> Map<String,Integer>
        # List<String> -> List<String> (no change)
        result = []
        inside_generics = 0
        i = 0

        while i < len(type_str):
            char = type_str[i]

            if char == "<":
                inside_generics += 1
                result.append(char)
            elif char == ">":
                inside_generics -= 1
                result.append(char)
            elif char == "," and inside_generics > 0:
                result.append(char)
                # Skip any following spaces
                i += 1
                while i < len(type_str) and type_str[i].isspace():
                    i += 1
                i -= 1  # Back up one since we'll increment at the end of loop
            else:
                result.append(char)

            i += 1

        return "".join(result)

    def _extract_methods_with_lines(
        self, content: str, commit_sha: str | None = None
    ) -> dict[str, tuple[int, int]]:
        """
        Extract methods with their line ranges using Spoon.

        Args:
            content: Java source code content
            commit_sha: Optional commit SHA for caching

        Returns:
            Dict mapping method signature to (start_line, end_line)
        """
        # Check cache first
        if commit_sha and commit_sha in self.method_cache:
            return self.method_cache[commit_sha]

        methods = {}
        import tempfile

        try:
            # Write content to temporary file for Spoon analysis
            with tempfile.NamedTemporaryFile(mode="w", suffix=".java", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                # Use hybrid analyzer to get method information with line numbers
                result = self.dependency_analyzer.analyze_class(tmp_path)
                if result:
                    # Extract method signatures with line ranges
                    for method in result.methods:
                        if method.start_line and method.end_line:
                            methods[method.signature] = (method.start_line, method.end_line)

                    # Include constructors
                    for ctor in result.constructors:
                        if ctor.start_line and ctor.end_line:
                            methods[ctor.signature] = (ctor.start_line, ctor.end_line)
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        except Exception as e:
            self.logger.debug(f"Failed to extract methods with Spoon, using fallback: {e}")
            # Fallback to regex-based extraction
            methods = self._extract_methods_with_lines_simple(content)

        # Cache the results
        if commit_sha and methods:
            self.method_cache[commit_sha] = methods

        return methods

    def _extract_methods_with_lines_simple(self, content: str) -> dict[str, tuple[int, int]]:
        """
        Simple regex-based method extraction with line numbers as fallback.

        Returns:
            Dict mapping method signature to (start_line, end_line)
        """
        methods = {}
        lines = content.split("\n")

        # Match method declarations - now handles generic return types
        method_pattern = r"^\s*(?:public|private|protected)?\s*(?:static)?\s*(?:final)?\s*(?:<[^>]+>)?\s*([\w.<>]+(?:<[^>]+>)?)\s+(\w+)\s*\(([^)]*)\)\s*\{"

        for i, line in enumerate(lines, 1):
            match = re.search(method_pattern, line)
            if match:
                return_type = match.group(1)
                method_name = match.group(2)
                params = match.group(3).strip()

                # Skip class declarations
                if return_type in ["class", "interface", "enum", "record"]:
                    continue

                # Build signature
                if params:
                    param_types = self._extract_param_types(params)
                    signature = f"{method_name}({','.join(param_types)})"
                else:
                    signature = f"{method_name}()"

                # Find end of method by counting braces
                end_line = self._find_method_end(lines, i - 1)
                methods[signature] = (i, end_line)

        return methods

    def _find_method_end(self, lines: list[str], start_idx: int) -> int:
        """Find the end line of a method by counting braces."""
        brace_count = 0
        in_method = False

        for i in range(start_idx, len(lines)):
            line = lines[i]
            for char in line:
                if char == "{":
                    brace_count += 1
                    in_method = True
                elif char == "}":
                    brace_count -= 1
                    if in_method and brace_count == 0:
                        return i + 1

        return len(lines)

    def _calculate_coupling_strengths(self, evo_data: EvolutionaryData):
        """
        Calculate evolutionary coupling strength between methods.

        Uses formula: coupling(m1, m2) = commits_both / sqrt(commits_m1 * commits_m2)
        Filters by minimum coupling threshold.
        """
        for (m1, m2), cochange_count in evo_data.cochange_matrix.items():
            commits_m1 = evo_data.method_commits.get(m1, 0)
            commits_m2 = evo_data.method_commits.get(m2, 0)

            if commits_m1 > 0 and commits_m2 > 0:
                coupling = cochange_count / np.sqrt(commits_m1 * commits_m2)

                # Apply minimum coupling threshold filter
                if coupling >= self.min_coupling_threshold:
                    evo_data.coupling_strengths[(m1, m2)] = coupling
                    evo_data.coupling_strengths[(m2, m1)] = coupling  # Symmetric

    def get_coupling_strength(
        self, evo_data: EvolutionaryData, method1: str, method2: str
    ) -> float:
        """
        Get evolutionary coupling strength between two methods.

        Args:
            evo_data: EvolutionaryData object
            method1: First method signature
            method2: Second method signature

        Returns:
            Coupling strength (0.0 if no coupling)
        """
        if method1 == method2:
            return 0.0

        key = (method1, method2) if method1 < method2 else (method2, method1)
        return evo_data.coupling_strengths.get(key, 0.0)

    def print_analysis_metrics(self):
        """Print metrics from the hybrid dependency analyzer."""
        if hasattr(self.dependency_analyzer, "metrics"):
            self.logger.info("=" * 80)
            self.logger.info("EVOLUTIONARY MINER - DEPENDENCY ANALYZER METRICS")
            self.logger.info("=" * 80)
            self.logger.info(self.dependency_analyzer.metrics.get_summary())
            self.logger.info(
                f"Spoon Success Rate: {self.dependency_analyzer.metrics.get_spoon_success_rate():.1f}%"
            )
            self.logger.info(
                f"Fallback Usage Rate: {self.dependency_analyzer.metrics.get_fallback_usage_rate():.1f}%"
            )
            self.logger.info("=" * 80)

    def _get_cache_key(
        self, class_file: str, window_months: int, min_commits: int, repo_signature: str
    ) -> str:
        """Generate cache key for a class file."""
        # Include configuration parameters in cache key to invalidate on config change
        config_str = f"{self.min_coupling_threshold}:{self.max_changeset_size}:{self.min_revisions}"
        key_str = f"{class_file}:{window_months}:{min_commits}:{config_str}:{repo_signature}"
        return hashlib.md5(key_str.encode()).hexdigest()  # nosec

    def _is_cache_valid(self, cache_key: str, ttl_days: int = 7) -> bool:
        """Check if cached data is still valid."""
        if not self.cache_dir:
            return False

        cache_file = self.cache_dir / f"{cache_key}.pkl"
        if not cache_file.exists():
            return False

        # Check age
        age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        return age.days < ttl_days

    def _load_from_cache(self, cache_key: str) -> EvolutionaryData | None:
        """Load cached evolutionary data."""
        if not self.cache_dir:
            return None

        cache_file = self.cache_dir / f"{cache_key}.pkl"
        try:
            with open(cache_file, "rb") as f:
                return pickle.load(f)  # nosec
        except Exception as e:
            self.logger.warning(f"Failed to load cache: {e}")
            return None

    def _save_to_cache(self, cache_key: str, data: EvolutionaryData):
        """Save evolutionary data to cache."""
        if not self.cache_dir:
            return

        cache_file = self.cache_dir / f"{cache_key}.pkl"
        try:
            with open(cache_file, "wb") as f:
                pickle.dump(data, f)

            # Auto-cleanup old/large cache entries
            self._cleanup_cache()
        except Exception as e:
            self.logger.warning(f"Failed to save cache: {e}")

    def _cleanup_cache(self, max_age_days: int = 30, max_size_mb: int = 100):
        """
        Clean up old and excessive cache files to prevent disk bloat.

        Args:
            max_age_days: Remove files older than this (default 30 days)
            max_size_mb: Maximum total cache size in MB (default 100MB)
        """
        if not self.cache_dir or not self.cache_dir.exists():
            return

        try:
            cache_files = list(self.cache_dir.glob("*.pkl"))
            if not cache_files:
                return

            now = datetime.now()
            files_with_info = []
            total_size = 0

            for cache_file in cache_files:
                try:
                    stat = cache_file.stat()
                    age_days = (now - datetime.fromtimestamp(stat.st_mtime)).days
                    size_bytes = stat.st_size
                    files_with_info.append((cache_file, age_days, size_bytes))
                    total_size += size_bytes
                except Exception:
                    continue

            # Remove files older than max_age_days
            removed_count = 0
            for cache_file, age_days, size_bytes in files_with_info:
                if age_days > max_age_days:
                    try:
                        cache_file.unlink()
                        total_size -= size_bytes
                        removed_count += 1
                    except Exception:
                        pass

            # If still over size limit, remove oldest files first
            max_size_bytes = max_size_mb * 1024 * 1024
            if total_size > max_size_bytes:
                # Sort by age (oldest first)
                files_with_info.sort(key=lambda x: x[1], reverse=True)

                for cache_file, age_days, size_bytes in files_with_info:
                    if total_size <= max_size_bytes:
                        break
                    if cache_file.exists():
                        try:
                            cache_file.unlink()
                            total_size -= size_bytes
                            removed_count += 1
                        except Exception:
                            pass

            if removed_count > 0:
                self.logger.info(
                    f"Cache cleanup: removed {removed_count} old/excess files. "
                    f"Current cache size: {total_size / (1024*1024):.1f}MB"
                )

        except Exception as e:
            self.logger.debug(f"Cache cleanup failed: {e}")

    def _get_repo_signature(self, repo: Repo, class_file: str) -> str:
        """Compute a signature for the repo state relevant to caching."""
        try:
            head_commit = repo.head.commit.hexsha
        except Exception:
            head_commit = "EMPTY"

        file_signature = "MISSING"
        try:
            tree = repo.head.commit.tree
            blob = tree / class_file
            file_signature = blob.hexsha
        except Exception:
            file_signature = "MISSING"

        return f"{head_commit}:{file_signature}"

    def get_sum_of_coupling(
        self, evo_data: EvolutionaryData, top_n: int | None = None
    ) -> list[tuple[str, float]]:
        """
        Calculate sum-of-coupling for each method (Code-Maat-inspired).

        Sum-of-coupling identifies "hub" methods that are coupled with many other methods.
        These are often good candidates for refactoring as they indicate high interconnectedness.

        Args:
            evo_data: EvolutionaryData object
            top_n: If specified, return only top N methods. If None, return all.

        Returns:
            List of (method_signature, sum_of_coupling) tuples, sorted by sum descending
        """
        sum_of_coupling: dict[str, float] = {}

        # Sum all coupling strengths for each method
        for (m1, m2), strength in evo_data.coupling_strengths.items():
            sum_of_coupling[m1] = sum_of_coupling.get(m1, 0.0) + strength
            sum_of_coupling[m2] = sum_of_coupling.get(m2, 0.0) + strength

        # Sort by sum of coupling (descending)
        sorted_methods = sorted(sum_of_coupling.items(), key=lambda x: x[1], reverse=True)

        # Return top N if specified
        if top_n is not None:
            return sorted_methods[:top_n]
        return sorted_methods

    def get_method_hotspots(
        self, evo_data: EvolutionaryData, top_n: int = 10, min_commits: int = 3
    ) -> list[tuple[str, int, float]]:
        """
        Identify method hotspots (frequently changed + highly coupled).

        Hotspots combine change frequency with coupling to identify methods that:
        1. Change frequently (high revision count)
        2. Are highly coupled with other methods (high sum-of-coupling)

        These are prime refactoring candidates as they:
        - Cause frequent merge conflicts (high changes)
        - Impact many other methods (high coupling)
        - Indicate design issues

        Args:
            evo_data: EvolutionaryData object
            top_n: Number of hotspots to return
            min_commits: Minimum commits to consider a method

        Returns:
            List of (method_signature, commit_count, hotspot_score) tuples
        """
        # Get sum-of-coupling for all methods
        sum_of_coupling_data = dict(self.get_sum_of_coupling(evo_data))

        # Calculate hotspot score: commits * sum_of_coupling
        hotspots = []
        for method, commits in evo_data.method_commits.items():
            if commits >= min_commits:
                coupling_sum = sum_of_coupling_data.get(method, 0.0)
                hotspot_score = commits * coupling_sum
                hotspots.append((method, commits, hotspot_score))

        # Sort by hotspot score (descending)
        hotspots.sort(key=lambda x: x[2], reverse=True)

        return hotspots[:top_n]

    def mine_cross_file_method_cochanges(
        self, class_files: list[str], repo_path: str, window_months: int = 12, min_commits: int = 2
    ) -> EvolutionaryData:
        """
        Mine method co-changes across MULTIPLE files (cross-file coupling).

        This extends the single-file analysis to track method coupling across file boundaries.
        Useful for identifying cross-module dependencies and refactoring opportunities.

        Args:
            class_files: List of class file paths (relative to repo root)
            repo_path: Path to Git repository
            window_months: How many months back to look
            min_commits: Minimum commits for a method to be considered

        Returns:
            EvolutionaryData object with cross-file coupling information
            Note: method_names will be qualified with file paths (e.g., "File.java::method(int)")
        """
        self.logger.info(f"Mining cross-file evolutionary coupling for {len(class_files)} files")

        try:
            repo = Repo(repo_path)
        except Exception as e:
            self.logger.error(f"Failed to open repository {repo_path}: {e}")
            return EvolutionaryData(class_file="<multiple>")

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=window_months * 30)

        # Get all commits affecting ANY of these files
        all_commits_map: dict[str, list[git.Commit]] = {}
        all_commits_set = set()

        for file_path in class_files:
            normalized_path = Path(file_path).as_posix()
            commits = self._get_file_commits(repo, normalized_path, start_date, end_date)
            all_commits_map[normalized_path] = commits
            all_commits_set.update(commits)

        if not all_commits_set:
            self.logger.warning(f"No commits found for any of the {len(class_files)} files")
            return EvolutionaryData(class_file="<multiple>")

        all_commits = sorted(all_commits_set, key=lambda c: c.committed_datetime)
        self.logger.info(f"Found {len(all_commits)} commits affecting {len(class_files)} files")

        # Track cross-file method changes
        evo_data = EvolutionaryData(class_file="<multiple>", total_commits=len(all_commits))

        for commit in all_commits:
            # Extract changed methods from ALL files in this commit
            all_changed_methods = []

            for file_path in class_files:
                normalized_path = Path(file_path).as_posix()
                changed_methods = self._extract_changed_methods(repo, commit, normalized_path)

                # Qualify methods with file name to distinguish cross-file
                for method in changed_methods:
                    qualified_method = f"{normalized_path}::{method}"
                    all_changed_methods.append(qualified_method)

            # Skip if too many methods changed (likely refactoring)
            if len(all_changed_methods) > self.max_changeset_size:
                self.logger.debug(
                    f"Skipping large cross-file changeset: {len(all_changed_methods)} methods "
                    f"(max: {self.max_changeset_size})"
                )
                continue

            # Update method commit counts
            for method in all_changed_methods:
                evo_data.method_names.add(method)
                evo_data.method_commits[method] = evo_data.method_commits.get(method, 0) + 1

            # Update co-change matrix (cross-file!)
            for m1 in all_changed_methods:
                for m2 in all_changed_methods:
                    if m1 < m2:  # Only store once (ordered pair)
                        key = (m1, m2)
                        evo_data.cochange_matrix[key] = evo_data.cochange_matrix.get(key, 0) + 1

        # Filter methods by minimum commits
        min_threshold = max(min_commits, self.min_revisions)
        filtered_methods = {
            m for m, count in evo_data.method_commits.items() if count >= min_threshold
        }
        evo_data.method_names = filtered_methods

        # Calculate coupling strengths
        self._calculate_coupling_strengths(evo_data)

        self.logger.info(
            f"Found {len(evo_data.method_names)} methods across {len(class_files)} files "
            f"with >= {min_commits} commits"
        )

        return evo_data
