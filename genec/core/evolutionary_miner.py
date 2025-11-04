"""Evolutionary coupling miner using Git history."""

import os
import hashlib
import pickle
from dataclasses import dataclass, field
from typing import Dict, Set, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import re

import git
from git import Repo, GitCommandError
import numpy as np

from genec.parsers.java_parser import JavaParser
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class EvolutionaryData:
    """Evolutionary coupling data extracted from Git history."""
    class_file: str
    method_names: Set[str] = field(default_factory=set)
    method_commits: Dict[str, int] = field(default_factory=dict)  # method -> commit count
    cochange_matrix: Dict[Tuple[str, str], int] = field(default_factory=dict)  # (m1, m2) -> count
    coupling_strengths: Dict[Tuple[str, str], float] = field(default_factory=dict)
    total_commits: int = 0


class EvolutionaryMiner:
    """Mines evolutionary coupling from Git commit history."""

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the evolutionary miner.

        Args:
            cache_dir: Directory for caching mining results
        """
        self.parser = JavaParser()
        self.logger = get_logger(self.__class__.__name__)
        self.cache_dir = Path(cache_dir) if cache_dir else None

        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def mine_method_cochanges(
        self,
        class_file: str,
        repo_path: str,
        window_months: int = 12,
        min_commits: int = 2
    ) -> EvolutionaryData:
        """
        Mine method co-changes from Git history.

        Args:
            class_file: Path to class file (relative to repo root)
            repo_path: Path to Git repository
            window_months: How many months back to look
            min_commits: Minimum commits for a method to be considered

        Returns:
            EvolutionaryData object with coupling information
        """
        self.logger.info(f"Mining evolutionary coupling for {class_file}")
        normalized_class_file = Path(class_file).as_posix() if class_file else class_file

        try:
            repo = Repo(repo_path)
        except Exception as e:
            self.logger.error(f"Failed to open repository {repo_path}: {e}")
            return EvolutionaryData(class_file=normalized_class_file)

        repo_signature = self._get_repo_signature(repo, normalized_class_file)

        # Check cache
        cache_key = self._get_cache_key(normalized_class_file, window_months, repo_signature)
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

        for commit in commits:
            changed_methods = self._extract_changed_methods(repo, commit, normalized_class_file)

            # Update method commit counts
            for method in changed_methods:
                evo_data.method_names.add(method)
                evo_data.method_commits[method] = evo_data.method_commits.get(method, 0) + 1

            # Update co-change matrix
            for m1 in changed_methods:
                for m2 in changed_methods:
                    if m1 < m2:  # Only store once (ordered pair)
                        key = (m1, m2)
                        evo_data.cochange_matrix[key] = evo_data.cochange_matrix.get(key, 0) + 1

        # Filter methods by minimum commits
        filtered_methods = {m for m, count in evo_data.method_commits.items() if count >= min_commits}
        evo_data.method_names = filtered_methods

        # Calculate coupling strengths
        self._calculate_coupling_strengths(evo_data)

        self.logger.info(
            f"Found {len(evo_data.method_names)} methods with >= {min_commits} commits"
        )

        # Cache the results
        if self.cache_dir:
            self._save_to_cache(cache_key, evo_data)

        return evo_data

    def _get_file_commits(
        self,
        repo: Repo,
        file_path: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[git.Commit]:
        """Get all commits affecting a file within a date range."""
        commits = []

        try:
            # Get commits for the file
            for commit in repo.iter_commits(paths=file_path, since=start_date.isoformat()):
                if commit.committed_datetime.replace(tzinfo=None) <= end_date:
                    commits.append(commit)
        except GitCommandError as e:
            self.logger.error(f"Git command error: {e}")

        return commits

    def _extract_changed_methods(
        self,
        repo: Repo,
        commit: git.Commit,
        file_path: str
    ) -> Set[str]:
        """
        Extract methods that changed in a specific commit.

        Args:
            repo: Git repository
            commit: Commit to analyze
            file_path: Path to file

        Returns:
            Set of changed method names
        """
        changed_methods = set()

        try:
            # Get the diff for this commit
            if not commit.parents:
                # Initial commit - consider all methods as changed
                try:
                    file_content = (commit.tree / file_path).data_stream.read().decode('utf-8')
                    methods = self._extract_methods_from_content(file_content)
                    return set(methods)
                except:
                    return set()

            parent = commit.parents[0]

            try:
                # Get file contents before and after
                old_content = (parent.tree / file_path).data_stream.read().decode('utf-8')
                new_content = (commit.tree / file_path).data_stream.read().decode('utf-8')

                # Get diff
                diff = repo.git.diff(parent.hexsha, commit.hexsha, file_path, unified=0)

                # Extract changed line ranges
                changed_lines = self._extract_changed_lines(diff)

                # Get methods in both versions
                old_methods = self._extract_methods_with_lines(old_content)
                new_methods = self._extract_methods_with_lines(new_content)

                # Check which methods overlap with changed lines
                for method, (start, end) in new_methods.items():
                    for changed_start, changed_end in changed_lines:
                        if not (end < changed_start or start > changed_end):
                            # Method overlaps with changed lines
                            changed_methods.add(method)
                            break

            except Exception as e:
                self.logger.debug(f"Error processing diff: {e}")

        except Exception as e:
            self.logger.debug(f"Error extracting changed methods: {e}")

        return changed_methods

    def _extract_changed_lines(self, diff: str) -> List[Tuple[int, int]]:
        """
        Extract changed line ranges from unified diff.

        Returns:
            List of (start_line, end_line) tuples
        """
        changed_ranges = []

        # Parse diff hunks: @@ -start,count +start,count @@
        hunk_pattern = r'@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@'

        for match in re.finditer(hunk_pattern, diff):
            start = int(match.group(1))
            count = int(match.group(2)) if match.group(2) else 1
            end = start + count - 1
            changed_ranges.append((start, end))

        return changed_ranges

    def _extract_methods_from_content(self, content: str) -> List[str]:
        """Extract method names from Java source content."""
        methods = []

        try:
            tree = self.parser.parse_file_content(content)
            if tree:
                for path, node in tree.filter(javalang.tree.MethodDeclaration):
                    methods.append(node.name)
                for path, node in tree.filter(javalang.tree.ConstructorDeclaration):
                    methods.append(node.name)
        except:
            pass

        return methods

    def _extract_methods_with_lines(self, content: str) -> Dict[str, Tuple[int, int]]:
        """
        Extract methods with their line ranges.

        Returns:
            Dict mapping method name to (start_line, end_line)
        """
        methods = {}
        lines = content.split('\n')

        # Simple regex-based extraction as fallback
        method_pattern = r'^\s*(?:public|private|protected)?\s*(?:static)?\s*(?:\w+\s+)+(\w+)\s*\([^)]*\)\s*\{'

        for i, line in enumerate(lines, 1):
            match = re.search(method_pattern, line)
            if match:
                method_name = match.group(1)
                # Find end of method by counting braces
                end_line = self._find_method_end(lines, i - 1)
                methods[method_name] = (i, end_line)

        return methods

    def _find_method_end(self, lines: List[str], start_idx: int) -> int:
        """Find the end line of a method by counting braces."""
        brace_count = 0
        in_method = False

        for i in range(start_idx, len(lines)):
            line = lines[i]
            for char in line:
                if char == '{':
                    brace_count += 1
                    in_method = True
                elif char == '}':
                    brace_count -= 1
                    if in_method and brace_count == 0:
                        return i + 1

        return len(lines)

    def _calculate_coupling_strengths(self, evo_data: EvolutionaryData):
        """
        Calculate evolutionary coupling strength between methods.

        Uses formula: coupling(m1, m2) = commits_both / sqrt(commits_m1 * commits_m2)
        """
        for (m1, m2), cochange_count in evo_data.cochange_matrix.items():
            commits_m1 = evo_data.method_commits.get(m1, 0)
            commits_m2 = evo_data.method_commits.get(m2, 0)

            if commits_m1 > 0 and commits_m2 > 0:
                coupling = cochange_count / np.sqrt(commits_m1 * commits_m2)
                evo_data.coupling_strengths[(m1, m2)] = coupling
                evo_data.coupling_strengths[(m2, m1)] = coupling  # Symmetric

    def get_coupling_strength(self, evo_data: EvolutionaryData, method1: str, method2: str) -> float:
        """
        Get evolutionary coupling strength between two methods.

        Args:
            evo_data: EvolutionaryData object
            method1: First method name
            method2: Second method name

        Returns:
            Coupling strength (0.0 if no coupling)
        """
        if method1 == method2:
            return 0.0

        key = (method1, method2) if method1 < method2 else (method2, method1)
        return evo_data.coupling_strengths.get(key, 0.0)

    def _get_cache_key(self, class_file: str, window_months: int, repo_signature: str) -> str:
        """Generate cache key for a class file."""
        key_str = f"{class_file}:{window_months}:{repo_signature}"
        return hashlib.md5(key_str.encode()).hexdigest()

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

    def _load_from_cache(self, cache_key: str) -> Optional[EvolutionaryData]:
        """Load cached evolutionary data."""
        if not self.cache_dir:
            return None

        cache_file = self.cache_dir / f"{cache_key}.pkl"
        try:
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to load cache: {e}")
            return None

    def _save_to_cache(self, cache_key: str, data: EvolutionaryData):
        """Save evolutionary data to cache."""
        if not self.cache_dir:
            return

        cache_file = self.cache_dir / f"{cache_key}.pkl"
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            self.logger.warning(f"Failed to save cache: {e}")

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
