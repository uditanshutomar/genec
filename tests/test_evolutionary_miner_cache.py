"""Tests for EvolutionaryMiner caching behaviour."""

from pathlib import Path

from git import Repo

from genec.core.evolutionary_miner import EvolutionaryMiner


JAVA_TEMPLATE_INITIAL = """\
public class Sample {
    private int value;

    public void setValue(int newValue) {
        value = newValue;
    }
}
"""

JAVA_TEMPLATE_UPDATED = """\
public class Sample {
    private int value;

    public void setValue(int newValue) {
        value = newValue;
    }

    public void increment(int delta) {
        value += delta;
    }
}
"""


def _init_repo(repo_path: Path) -> Repo:
    repo = Repo.init(repo_path)
    with repo.config_writer() as cw:
        cw.set_value("user", "name", "GenECTester")
        cw.set_value("user", "email", "tester@example.com")
    return repo


def _commit(repo: Repo, rel_path: Path, message: str):
    repo.index.add([rel_path.as_posix()])
    repo.index.commit(message)


def test_evolutionary_cache_invalidates_on_new_commit(tmp_path):
    """Cache should be invalidated when HEAD changes."""
    repo = _init_repo(tmp_path)

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    class_rel = Path("src/Sample.java")
    class_file = tmp_path / class_rel

    class_file.write_text(JAVA_TEMPLATE_INITIAL, encoding="utf-8")
    _commit(repo, class_rel, "initial")

    cache_dir = tmp_path / "cache"
    miner = EvolutionaryMiner(cache_dir=str(cache_dir))

    first_result = miner.mine_method_cochanges(
        class_rel.as_posix(),
        str(tmp_path),
        window_months=12,
        min_commits=1,
    )

    assert first_result.total_commits == 1

    class_file.write_text(JAVA_TEMPLATE_UPDATED, encoding="utf-8")
    _commit(repo, class_rel, "add increment method")

    second_result = miner.mine_method_cochanges(
        class_rel.as_posix(),
        str(tmp_path),
        window_months=12,
        min_commits=1,
    )

    assert second_result.total_commits == 2
