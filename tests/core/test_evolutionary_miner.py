"""Tests for genec.core.evolutionary_miner module."""

import os
import pickle  # nosec - testing existing pickle-based cache in the module
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import numpy as np
import pytest

from genec.core.evolutionary_miner import (
    EvolutionaryData,
    EvolutionaryMiner,
    process_commit_worker,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_commit(hexsha: str, parents=None, committed_datetime=None, tree=None):
    """Create a mock git.Commit object."""
    commit = MagicMock()
    commit.hexsha = hexsha
    commit.parents = parents if parents is not None else [MagicMock()]
    if committed_datetime is None:
        committed_datetime = datetime.now(timezone.utc)
    commit.committed_datetime = committed_datetime
    if tree is not None:
        commit.tree = tree
    else:
        commit.tree = MagicMock()
    return commit


SAMPLE_JAVA = """\
public class Calculator {
    private int total;

    public void add(int x) {
        total += x;
    }

    public void subtract(int y) {
        total -= y;
    }

    public int getTotal() {
        return total;
    }
}
"""


# ---------------------------------------------------------------------------
# EvolutionaryData dataclass
# ---------------------------------------------------------------------------

class TestEvolutionaryData:
    def test_default_fields(self):
        data = EvolutionaryData(class_file="Foo.java")
        assert data.class_file == "Foo.java"
        assert data.method_names == set()
        assert data.method_commits == {}
        assert data.cochange_matrix == {}
        assert data.coupling_strengths == {}
        assert data.total_commits == 0


# ---------------------------------------------------------------------------
# EvolutionaryMiner construction
# ---------------------------------------------------------------------------

class TestEvolutionaryMinerInit:
    def test_default_params(self):
        with patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer"):
            miner = EvolutionaryMiner()
        assert miner.min_coupling_threshold == 0.3
        assert miner.max_changeset_size == 30
        assert miner.min_revisions == 2
        assert miner.cache_dir is None

    def test_cache_dir_created(self):
        with tempfile.TemporaryDirectory() as td:
            cache_path = os.path.join(td, "cache_subdir")
            with patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer"):
                miner = EvolutionaryMiner(cache_dir=cache_path)
            assert miner.cache_dir == Path(cache_path)
            assert miner.cache_dir.exists()


# ---------------------------------------------------------------------------
# mine_method_cochanges
# ---------------------------------------------------------------------------

class TestMineMethodCochanges:
    """Tests for the main entry point."""

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_returns_empty_for_no_commits(self, mock_hda):
        """Class file with no commits should return empty EvolutionaryData."""
        miner = EvolutionaryMiner()

        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([])

        with patch("genec.core.evolutionary_miner.Repo", return_value=mock_repo):
            result = miner.mine_method_cochanges(
                "src/Foo.java", "/fake/repo", show_metrics=False
            )

        assert isinstance(result, EvolutionaryData)
        assert result.class_file == "src/Foo.java"
        assert result.total_commits == 0
        assert result.method_names == set()

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_handles_nonexistent_repo(self, mock_hda):
        """Should return empty EvolutionaryData when repo path doesn't exist."""
        miner = EvolutionaryMiner()

        with patch(
            "genec.core.evolutionary_miner.Repo",
            side_effect=Exception("Not a git repository"),
        ):
            result = miner.mine_method_cochanges(
                "src/Foo.java", "/nonexistent/repo", show_metrics=False
            )

        assert isinstance(result, EvolutionaryData)
        assert result.total_commits == 0

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_handles_nonexistent_file(self, mock_hda):
        """When the file has no commits, should return empty data."""
        miner = EvolutionaryMiner()

        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([])

        with patch("genec.core.evolutionary_miner.Repo", return_value=mock_repo):
            result = miner.mine_method_cochanges(
                "src/NonExistent.java", "/fake/repo", show_metrics=False
            )

        assert isinstance(result, EvolutionaryData)
        assert result.total_commits == 0

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_finds_cochanges_between_methods(self, mock_hda):
        """Two methods changed in the same commit should produce co-change data."""
        miner = EvolutionaryMiner(min_revisions=1)

        now = datetime.now(timezone.utc)
        commit1 = _make_mock_commit("abc123", committed_datetime=now)
        commit2 = _make_mock_commit("def456", committed_datetime=now - timedelta(days=1))

        mock_repo = MagicMock()
        mock_repo.head.commit.hexsha = "abc123"
        mock_repo.head.commit.tree.__truediv__ = MagicMock(side_effect=KeyError("not found"))

        with (
            patch("genec.core.evolutionary_miner.Repo", return_value=mock_repo),
            patch.object(miner, "_get_file_commits", return_value=[commit1, commit2]),
            patch("genec.core.evolutionary_miner.concurrent.futures.ProcessPoolExecutor") as mock_pool,
        ):
            # Simulate executor context manager
            mock_executor = MagicMock()
            mock_pool.return_value.__enter__ = MagicMock(return_value=mock_executor)
            mock_pool.return_value.__exit__ = MagicMock(return_value=False)

            # Create futures that return changed method sets
            future1 = MagicMock()
            future1.result.return_value = {"add(int)", "subtract(int)"}
            future2 = MagicMock()
            future2.result.return_value = {"add(int)", "getTotal()"}

            mock_executor.submit.side_effect = [future1, future2]

            # as_completed returns the futures
            with patch(
                "genec.core.evolutionary_miner.concurrent.futures.as_completed",
                return_value=[future1, future2],
            ):
                result = miner.mine_method_cochanges(
                    "src/Calc.java",
                    "/fake/repo",
                    min_commits=1,
                    show_metrics=False,
                )

        # Both commits returned methods; check co-change matrix
        assert result.total_commits == 2
        # add(int) appeared in 2 commits
        assert result.method_commits.get("add(int)") == 2
        # (add(int), subtract(int)) co-changed in commit1
        key = ("add(int)", "subtract(int)")
        assert result.cochange_matrix.get(key, 0) == 1

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_respects_window_months(self, mock_hda):
        """Commits outside the window should be excluded by _get_file_commits."""
        miner = EvolutionaryMiner()

        now = datetime.now(timezone.utc)
        recent_commit = _make_mock_commit("aaa111", committed_datetime=now)

        mock_repo = MagicMock()
        mock_repo.head.commit.hexsha = "aaa111"
        mock_repo.head.commit.tree.__truediv__ = MagicMock(side_effect=KeyError("nope"))

        # Patch _get_file_commits to return only the recent commit (simulating
        # that Git filtered out old commits via the since= parameter)
        with (
            patch("genec.core.evolutionary_miner.Repo", return_value=mock_repo),
            patch.object(miner, "_get_file_commits", return_value=[recent_commit]),
            patch("genec.core.evolutionary_miner.concurrent.futures.ProcessPoolExecutor") as mock_pool,
        ):
            mock_executor = MagicMock()
            mock_pool.return_value.__enter__ = MagicMock(return_value=mock_executor)
            mock_pool.return_value.__exit__ = MagicMock(return_value=False)

            future1 = MagicMock()
            future1.result.return_value = {"doStuff()"}
            mock_executor.submit.side_effect = [future1]

            with patch(
                "genec.core.evolutionary_miner.concurrent.futures.as_completed",
                return_value=[future1],
            ):
                result = miner.mine_method_cochanges(
                    "src/Foo.java",
                    "/fake/repo",
                    window_months=6,
                    show_metrics=False,
                )

        # Only 1 commit should have been processed
        assert result.total_commits == 1

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_min_commits_filter(self, mock_hda):
        """Methods with fewer than min_commits should be filtered from method_names."""
        miner = EvolutionaryMiner(min_revisions=1)

        now = datetime.now(timezone.utc)
        commits = [
            _make_mock_commit(f"sha{i}", committed_datetime=now - timedelta(days=i))
            for i in range(5)
        ]

        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter(commits)
        mock_repo.head.commit.hexsha = "sha0"
        mock_repo.head.commit.tree.__truediv__ = MagicMock(side_effect=KeyError("nope"))

        with (
            patch("genec.core.evolutionary_miner.Repo", return_value=mock_repo),
            patch("genec.core.evolutionary_miner.concurrent.futures.ProcessPoolExecutor") as mock_pool,
        ):
            mock_executor = MagicMock()
            mock_pool.return_value.__enter__ = MagicMock(return_value=mock_executor)
            mock_pool.return_value.__exit__ = MagicMock(return_value=False)

            # "frequent()" appears in all 5, "rare()" in only 1
            futures = []
            for i in range(5):
                f = MagicMock()
                if i == 0:
                    f.result.return_value = {"frequent()", "rare()"}
                else:
                    f.result.return_value = {"frequent()"}
                futures.append(f)

            mock_executor.submit.side_effect = futures

            with patch(
                "genec.core.evolutionary_miner.concurrent.futures.as_completed",
                return_value=futures,
            ):
                result = miner.mine_method_cochanges(
                    "src/Foo.java",
                    "/fake/repo",
                    min_commits=3,
                    show_metrics=False,
                )

        # frequent() has 5 commits (>= max(3,1)=3), rare() has 1 (< 3)
        assert "frequent()" in result.method_names
        assert "rare()" not in result.method_names

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_cache_hit_avoids_git_calls(self, mock_hda):
        """Second call with same args should use cached result."""
        with tempfile.TemporaryDirectory() as td:
            miner = EvolutionaryMiner(cache_dir=td, min_revisions=1)

            # Pre-populate cache
            cached_data = EvolutionaryData(
                class_file="src/Cached.java",
                method_names={"cached()"},
                method_commits={"cached()": 10},
                total_commits=10,
            )

            mock_repo = MagicMock()
            mock_repo.head.commit.hexsha = "headsha"
            mock_repo.head.commit.tree.__truediv__ = MagicMock(side_effect=KeyError("x"))

            with patch("genec.core.evolutionary_miner.Repo", return_value=mock_repo):
                # Generate the cache key
                repo_sig = miner._get_repo_signature(mock_repo, "src/Cached.java")
                cache_key = miner._get_cache_key("src/Cached.java", 12, 2, repo_sig)

                # Write cache file (nosec - testing existing pickle cache)
                cache_file = Path(td) / f"{cache_key}.pkl"
                with open(cache_file, "wb") as f:
                    pickle.dump(cached_data, f)  # nosec

                # Call mine_method_cochanges -- should hit cache
                result = miner.mine_method_cochanges(
                    "src/Cached.java", "/fake/repo", show_metrics=False
                )

            assert result.class_file == "src/Cached.java"
            assert "cached()" in result.method_names
            # iter_commits should not have been called
            mock_repo.iter_commits.assert_not_called()


# ---------------------------------------------------------------------------
# _extract_changed_methods and changeset size filtering
# ---------------------------------------------------------------------------

class TestExtractChangedMethods:
    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_changeset_size_filtering(self, mock_hda):
        """Commits with too many changed methods should return empty set."""
        miner = EvolutionaryMiner(max_changeset_size=3)

        mock_repo = MagicMock()
        parent_commit = _make_mock_commit("parent_sha")
        commit = _make_mock_commit("commit_sha", parents=[parent_commit])

        # Mock file content retrieval
        old_blob = MagicMock()
        old_blob.data_stream.read.return_value = b"old content"
        new_blob = MagicMock()
        new_blob.data_stream.read.return_value = b"new content"

        parent_commit.tree.__truediv__ = MagicMock(return_value=old_blob)
        commit.tree.__truediv__ = MagicMock(return_value=new_blob)

        # Mock diff output with many hunks
        mock_repo.git.diff.return_value = (
            "@@ -1,5 +1,5 @@\n@@ -10,3 +10,3 @@\n@@ -20,2 +20,2 @@\n@@ -30,1 +30,1 @@"
        )

        # Return 5 methods (> max_changeset_size of 3)
        large_methods = {
            f"method{i}()": (i * 10, i * 10 + 5) for i in range(5)
        }

        with patch.object(
            miner, "_extract_methods_with_lines", return_value=large_methods
        ):
            result = miner._extract_changed_methods(mock_repo, commit, "Foo.java")

        # Should return empty set because changeset is too large
        assert result == set()

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_initial_commit_all_methods(self, mock_hda):
        """Initial commit (no parents) should treat all methods as changed."""
        miner = EvolutionaryMiner()

        commit = _make_mock_commit("init_sha", parents=[])

        # Mock tree lookup
        blob = MagicMock()
        blob.data_stream.read.return_value = SAMPLE_JAVA.encode("utf-8")
        commit.tree.__truediv__ = MagicMock(return_value=blob)

        with patch.object(
            miner, "_extract_methods_from_content", return_value=["add(int)", "subtract(int)"]
        ):
            result = miner._extract_changed_methods(MagicMock(), commit, "Calculator.java")

        assert "add(int)" in result
        assert "subtract(int)" in result


# ---------------------------------------------------------------------------
# _extract_changed_lines
# ---------------------------------------------------------------------------

class TestExtractChangedLines:
    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_parses_diff_hunks(self, mock_hda):
        miner = EvolutionaryMiner()

        diff = """\
@@ -10,3 +10,5 @@ some context
+added line
@@ -20,0 +22,1 @@ another context
+another added line"""

        result = miner._extract_changed_lines(diff)
        assert (10, 14) in result  # +10,5 -> lines 10..14
        assert (22, 22) in result  # +22,1 -> lines 22..22

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_single_line_hunk(self, mock_hda):
        miner = EvolutionaryMiner()
        diff = "@@ -5,1 +5 @@\n-removed"
        result = miner._extract_changed_lines(diff)
        # +5 with no count means count=1
        assert (5, 5) in result

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_empty_diff(self, mock_hda):
        miner = EvolutionaryMiner()
        assert miner._extract_changed_lines("") == []


# ---------------------------------------------------------------------------
# _extract_methods_simple and helpers
# ---------------------------------------------------------------------------

class TestExtractMethodsSimple:
    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_extracts_basic_methods(self, mock_hda):
        miner = EvolutionaryMiner()
        methods = miner._extract_methods_simple(SAMPLE_JAVA)

        sigs = set(methods)
        assert "add(int)" in sigs
        assert "subtract(int)" in sigs
        assert "getTotal()" in sigs

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_skips_class_declarations(self, mock_hda):
        miner = EvolutionaryMiner()
        code = "public class Foo extends Bar {"
        methods = miner._extract_methods_simple(code)
        assert methods == []

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_extracts_generic_param_types(self, mock_hda):
        miner = EvolutionaryMiner()
        code = "    public void process(Map<String, Integer> data) {"
        # _extract_methods_simple needs the opening brace variant
        methods = miner._extract_methods_simple(code)
        # Method pattern in _extract_methods_simple doesn't require {, but
        # let's check the plain version
        plain_code = "    public void process(Map<String, Integer> data)"
        methods2 = miner._extract_methods_simple(plain_code)
        # At least one should capture it
        all_methods = set(methods + methods2)
        assert any("process" in m for m in all_methods)


# ---------------------------------------------------------------------------
# _extract_param_types
# ---------------------------------------------------------------------------

class TestExtractParamTypes:
    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_simple_types(self, mock_hda):
        miner = EvolutionaryMiner()
        result = miner._extract_param_types("int x, String y")
        assert result == ["int", "String"]

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_generic_types(self, mock_hda):
        miner = EvolutionaryMiner()
        result = miner._extract_param_types("Map<String, Integer> map")
        assert len(result) == 1
        assert "Map<String,Integer>" in result[0]

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_empty_params(self, mock_hda):
        miner = EvolutionaryMiner()
        result = miner._extract_param_types("")
        assert result == []


# ---------------------------------------------------------------------------
# _calculate_coupling_strengths
# ---------------------------------------------------------------------------

class TestCalculateCouplingStrengths:
    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_coupling_formula(self, mock_hda):
        """coupling(m1,m2) = cochange / sqrt(commits_m1 * commits_m2)."""
        miner = EvolutionaryMiner(min_coupling_threshold=0.0)

        data = EvolutionaryData(
            class_file="Foo.java",
            method_commits={"a()": 10, "b()": 10},
            cochange_matrix={("a()", "b()"): 5},
        )
        miner._calculate_coupling_strengths(data)

        expected = 5 / np.sqrt(10 * 10)  # 0.5
        # FIX 2: coupling_strengths now stores only sorted key
        sorted_key = tuple(sorted(["a()", "b()"]))
        assert abs(data.coupling_strengths[sorted_key] - expected) < 1e-6
        # Reverse key should NOT exist (no longer stored)
        reverse_key = tuple(reversed(sorted_key))
        assert reverse_key not in data.coupling_strengths or reverse_key == sorted_key

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_coupling_threshold_filters(self, mock_hda):
        """Pairs below min_coupling_threshold should not appear."""
        miner = EvolutionaryMiner(min_coupling_threshold=0.8)

        data = EvolutionaryData(
            class_file="Foo.java",
            method_commits={"a()": 10, "b()": 10, "c()": 10},
            cochange_matrix={
                ("a()", "b()"): 9,   # 0.9 -- above threshold
                ("a()", "c()"): 1,   # 0.1 -- below threshold
            },
        )
        miner._calculate_coupling_strengths(data)

        assert ("a()", "b()") in data.coupling_strengths
        assert ("a()", "c()") not in data.coupling_strengths


# ---------------------------------------------------------------------------
# get_coupling_strength
# ---------------------------------------------------------------------------

class TestGetCouplingStrength:
    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_returns_zero_for_same_method(self, mock_hda):
        miner = EvolutionaryMiner()
        data = EvolutionaryData(class_file="X.java")
        assert miner.get_coupling_strength(data, "foo()", "foo()") == 0.0

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_returns_stored_value(self, mock_hda):
        miner = EvolutionaryMiner()
        # FIX 2: coupling_strengths now stores only sorted key
        data = EvolutionaryData(
            class_file="X.java",
            coupling_strengths={("a()", "b()"): 0.75},
        )
        assert miner.get_coupling_strength(data, "a()", "b()") == 0.75
        assert miner.get_coupling_strength(data, "b()", "a()") == 0.75

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_returns_zero_for_unknown_pair(self, mock_hda):
        miner = EvolutionaryMiner()
        data = EvolutionaryData(class_file="X.java")
        assert miner.get_coupling_strength(data, "x()", "y()") == 0.0


# ---------------------------------------------------------------------------
# Cache operations
# ---------------------------------------------------------------------------

class TestCacheOperations:
    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_save_and_load_cache(self, mock_hda):
        with tempfile.TemporaryDirectory() as td:
            miner = EvolutionaryMiner(cache_dir=td)

            data = EvolutionaryData(
                class_file="Bar.java",
                method_names={"m1()", "m2()"},
                total_commits=5,
            )
            cache_key = "test_key_123"
            miner._save_to_cache(cache_key, data)

            loaded = miner._load_from_cache(cache_key)
            assert loaded is not None
            assert loaded.class_file == "Bar.java"
            assert loaded.method_names == {"m1()", "m2()"}
            assert loaded.total_commits == 5

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_cache_validity(self, mock_hda):
        with tempfile.TemporaryDirectory() as td:
            miner = EvolutionaryMiner(cache_dir=td)

            # Non-existent key is invalid
            assert not miner._is_cache_valid("nonexistent")

            # Write a file and check validity
            cache_file = Path(td) / "valid_key.pkl"
            cache_file.write_bytes(b"dummy")
            assert miner._is_cache_valid("valid_key")

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_load_from_cache_no_cache_dir(self, mock_hda):
        miner = EvolutionaryMiner(cache_dir=None)
        assert miner._load_from_cache("any_key") is None

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_save_to_cache_no_cache_dir(self, mock_hda):
        miner = EvolutionaryMiner(cache_dir=None)
        # Should not raise
        miner._save_to_cache("key", EvolutionaryData(class_file="X.java"))

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_cache_cleanup_removes_old_files(self, mock_hda):
        with tempfile.TemporaryDirectory() as td:
            miner = EvolutionaryMiner(cache_dir=td)

            # Create a file with old modification time
            old_file = Path(td) / "old.pkl"
            old_file.write_bytes(b"data")
            old_time = (datetime.now() - timedelta(days=60)).timestamp()
            os.utime(old_file, (old_time, old_time))

            miner._cleanup_cache(max_age_days=30)
            assert not old_file.exists()


# ---------------------------------------------------------------------------
# process_commit_worker (module-level function)
# ---------------------------------------------------------------------------

class TestProcessCommitWorker:
    @patch("genec.core.evolutionary_miner.Repo")
    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_returns_empty_on_failure(self, mock_hda, mock_repo_cls):
        """Worker should return empty set when repo fails."""
        mock_repo_cls.side_effect = Exception("repo gone")
        result = process_commit_worker("/bad/path", "sha123", "Foo.java", 30)
        assert result == set()

    @patch("genec.core.evolutionary_miner.Repo")
    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_calls_extract_changed_methods(self, mock_hda, mock_repo_cls):
        """Worker should call _extract_changed_methods and return result."""
        mock_repo = MagicMock()
        mock_commit = MagicMock()
        mock_repo.commit.return_value = mock_commit
        mock_repo_cls.return_value = mock_repo

        with patch.object(
            EvolutionaryMiner,
            "_extract_changed_methods",
            return_value={"foo()", "bar()"},
        ):
            result = process_commit_worker("/fake/repo", "abc123", "Foo.java", 30)

        assert result == {"foo()", "bar()"}


# ---------------------------------------------------------------------------
# _normalize_generic_type
# ---------------------------------------------------------------------------

class TestNormalizeGenericType:
    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_removes_spaces_in_generics(self, mock_hda):
        miner = EvolutionaryMiner()
        assert miner._normalize_generic_type("Map<String, Integer>") == "Map<String,Integer>"

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_no_change_for_simple_types(self, mock_hda):
        miner = EvolutionaryMiner()
        assert miner._normalize_generic_type("String") == "String"
        assert miner._normalize_generic_type("List<String>") == "List<String>"


# ---------------------------------------------------------------------------
# _find_method_end
# ---------------------------------------------------------------------------

class TestFindMethodEnd:
    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_finds_closing_brace(self, mock_hda):
        miner = EvolutionaryMiner()
        lines = [
            "    public void foo() {",
            "        int x = 1;",
            "    }",
            "",
        ]
        end = miner._find_method_end(lines, 0)
        assert end == 3  # line 3 (1-indexed)

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_handles_nested_braces(self, mock_hda):
        miner = EvolutionaryMiner()
        lines = [
            "    public void foo() {",
            "        if (true) {",
            "            x = 1;",
            "        }",
            "    }",
        ]
        end = miner._find_method_end(lines, 0)
        assert end == 5  # line 5 (1-indexed)


# ---------------------------------------------------------------------------
# _get_cache_key
# ---------------------------------------------------------------------------

class TestGetCacheKey:
    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_different_params_produce_different_keys(self, mock_hda):
        miner = EvolutionaryMiner()
        key1 = miner._get_cache_key("Foo.java", 12, 2, "sig1")
        key2 = miner._get_cache_key("Foo.java", 6, 2, "sig1")
        key3 = miner._get_cache_key("Bar.java", 12, 2, "sig1")
        assert key1 != key2
        assert key1 != key3

    @patch("genec.core.evolutionary_miner.HybridDependencyAnalyzer")
    def test_same_params_produce_same_key(self, mock_hda):
        miner = EvolutionaryMiner()
        key1 = miner._get_cache_key("Foo.java", 12, 2, "sig1")
        key2 = miner._get_cache_key("Foo.java", 12, 2, "sig1")
        assert key1 == key2
