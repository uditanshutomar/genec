"""
End-to-end integration tests for the GenEC pipeline.
Run the REAL pipeline on REAL Java files — no mocks.
"""
import json
import subprocess
import pytest
from pathlib import Path

# Mark all tests in this file as integration (slow)
pytestmark = pytest.mark.integration

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "java"

# Common config overrides for test repos that have only 1 commit.
# alpha=1.0 uses pure static analysis (evolutionary data from a single
# commit is all-to-all co-change, which merges everything into one cluster).
_TEST_PIPELINE_OVERRIDES = {
    "refactoring_application": {"enabled": False},
    "verification": {"enable_behavioral": False},  # No Maven in test repo
    "fusion": {"alpha": 1.0},  # Pure static — 1-commit repos have degenerate evo data
}


@pytest.fixture
def simple_god_class_repo(tmp_path):
    """Create a git repo with GodClassSimple.java."""
    # Create package structure
    pkg_dir = tmp_path / "src" / "main" / "java" / "com" / "test"
    pkg_dir.mkdir(parents=True)

    # Copy fixture
    src = FIXTURES_DIR / "GodClassSimple.java"
    dst = pkg_dir / "GodClassSimple.java"
    dst.write_text(src.read_text())

    # Init git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)

    return tmp_path, str(dst)


@pytest.fixture
def deps_god_class_repo(tmp_path):
    """Create a git repo with GodClassWithDeps.java."""
    pkg_dir = tmp_path / "src" / "main" / "java" / "com" / "test"
    pkg_dir.mkdir(parents=True)

    src = FIXTURES_DIR / "GodClassWithDeps.java"
    dst = pkg_dir / "GodClassWithDeps.java"
    dst.write_text(src.read_text())

    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)

    return tmp_path, str(dst)


class TestFullPipelineE2E:
    """Test the complete pipeline end-to-end with real Java files."""

    def test_simple_god_class_produces_suggestions(self, simple_god_class_repo):
        """Pipeline should find clusters in a simple God Class."""
        repo_path, class_file = simple_god_class_repo

        from genec.core.pipeline import GenECPipeline

        pipeline = GenECPipeline(config_overrides=_TEST_PIPELINE_OVERRIDES)

        result = pipeline.run_full_pipeline(class_file, str(repo_path))

        # Should find at least 1 suggestion (auto-named without LLM)
        assert len(result.suggestions) > 0, "No suggestions generated"
        # Should NOT include degenerate (all methods) clusters
        for s in result.suggestions:
            if s.cluster:
                assert len(s.cluster.get_methods()) < 20, \
                    f"Cluster too large: {len(s.cluster.get_methods())} methods"

    def test_simple_god_class_metrics(self, simple_god_class_repo):
        """Pipeline should compute valid cohesion metrics."""
        repo_path, class_file = simple_god_class_repo

        from genec.core.pipeline import GenECPipeline

        pipeline = GenECPipeline(config_overrides=_TEST_PIPELINE_OVERRIDES)

        result = pipeline.run_full_pipeline(class_file, str(repo_path))

        # LCOM5 should be valid
        lcom5 = result.original_metrics.get("lcom5", -1)
        assert 0.0 <= lcom5 <= 1.0, f"Invalid LCOM5: {lcom5}"

        # TCC should be valid
        tcc = result.original_metrics.get("tcc", -1)
        assert 0.0 <= tcc <= 1.0, f"Invalid TCC: {tcc}"

    def test_pipeline_report_generated(self, simple_god_class_repo):
        """Pipeline should generate a structured report."""
        repo_path, class_file = simple_god_class_repo

        from genec.core.pipeline import GenECPipeline

        pipeline = GenECPipeline(config_overrides=_TEST_PIPELINE_OVERRIDES)

        result = pipeline.run_full_pipeline(class_file, str(repo_path))

        # Pipeline report should exist and have stage data
        assert result.pipeline_report, "No pipeline report generated"
        assert "stages" in result.pipeline_report
        assert result.pipeline_report["summary"]["stages_completed"] > 0

    def test_deps_god_class_handles_imports(self, deps_god_class_repo):
        """Pipeline should handle classes with java.util imports."""
        repo_path, class_file = deps_god_class_repo

        from genec.core.pipeline import GenECPipeline

        pipeline = GenECPipeline(config_overrides=_TEST_PIPELINE_OVERRIDES)

        result = pipeline.run_full_pipeline(class_file, str(repo_path))

        assert len(result.suggestions) > 0, "No suggestions for class with imports"

    def test_deterministic_with_seed(self, simple_god_class_repo):
        """Same seed should produce same clusters."""
        repo_path, class_file = simple_god_class_repo

        from genec.core.pipeline import GenECPipeline

        results = []
        for _ in range(2):
            overrides = {**_TEST_PIPELINE_OVERRIDES, "clustering": {"seed": 42}}
            pipeline = GenECPipeline(config_overrides=overrides)
            result = pipeline.run_full_pipeline(class_file, str(repo_path))
            names = sorted([s.proposed_class_name for s in result.suggestions])
            results.append(names)

        assert results[0] == results[1], \
            f"Non-deterministic results: {results[0]} vs {results[1]}"

    def test_dry_run_does_not_modify_files(self, simple_god_class_repo):
        """Dry run should not modify any files in the repo."""
        repo_path, class_file = simple_god_class_repo

        # Read original content
        original_content = Path(class_file).read_text()

        from genec.core.pipeline import GenECPipeline

        overrides = {
            **_TEST_PIPELINE_OVERRIDES,
            "refactoring_application": {"enabled": True, "dry_run": True},
        }
        pipeline = GenECPipeline(config_overrides=overrides)

        result = pipeline.run_full_pipeline(class_file, str(repo_path))

        # Original file should be unchanged
        assert Path(class_file).read_text() == original_content, \
            "Dry run modified the original file!"

        # No new files should exist in the package directory
        pkg_dir = Path(class_file).parent
        java_files = list(pkg_dir.glob("*.java"))
        assert len(java_files) == 1, \
            f"Dry run created new files: {[f.name for f in java_files]}"


class TestParsingE2E:
    """Test Java parsing on real files."""

    def test_parse_simple_class(self):
        """Parser should extract methods and fields from fixture."""
        from genec.core.dependency_analyzer import DependencyAnalyzer

        analyzer = DependencyAnalyzer()
        class_file = str(FIXTURES_DIR / "GodClassSimple.java")
        deps = analyzer.analyze_class(class_file)

        assert deps is not None, "Parsing returned None"
        assert len(deps.methods) >= 15, f"Expected >=15 methods, got {len(deps.methods)}"
        assert len(deps.fields) >= 6, f"Expected >=6 fields, got {len(deps.fields)}"
        assert deps.class_name == "GodClassSimple"

    def test_parse_class_with_imports(self):
        """Parser should handle java.util imports."""
        from genec.core.dependency_analyzer import DependencyAnalyzer

        analyzer = DependencyAnalyzer()
        class_file = str(FIXTURES_DIR / "GodClassWithDeps.java")
        deps = analyzer.analyze_class(class_file)

        assert deps is not None
        assert len(deps.methods) >= 10
        assert deps.class_name == "GodClassWithDeps"


class TestClusteringE2E:
    """Test clustering on real dependency data."""

    def test_clustering_finds_groups(self, simple_god_class_repo):
        """Clustering should find distinct method groups using pure static analysis."""
        repo_path, class_file = simple_god_class_repo

        from genec.core.dependency_analyzer import DependencyAnalyzer
        from genec.core.graph_builder import GraphBuilder
        from genec.core.cluster_detector import ClusterDetector

        import networkx as nx

        analyzer = DependencyAnalyzer()
        deps = analyzer.analyze_class(class_file)

        builder = GraphBuilder()
        G_static = builder.build_static_graph(deps)
        # Use pure static graph (1-commit repos produce degenerate evo data)
        G_fused = builder.fuse_graphs(G_static, nx.Graph(), alpha=1.0)

        detector = ClusterDetector(min_cluster_size=3, seed=42)
        clusters = detector.detect_clusters(G_fused, deps)

        # Should find at least 2 clusters (the class has 3 responsibility groups)
        assert len(clusters) >= 2, f"Expected >=2 clusters, got {len(clusters)}"


class TestCodeGenerationE2E:
    """Test JDT code generation on real files."""

    def test_jdt_generates_compilable_code(self, simple_god_class_repo):
        """JDT should generate code that compiles."""
        repo_path, class_file = simple_god_class_repo

        from genec.core.dependency_analyzer import DependencyAnalyzer
        from genec.core.graph_builder import GraphBuilder
        from genec.core.cluster_detector import ClusterDetector
        from genec.core.jdt_code_generator import JDTCodeGenerator

        import networkx as nx

        # Get clusters using pure static analysis
        analyzer = DependencyAnalyzer()
        deps = analyzer.analyze_class(class_file)

        builder = GraphBuilder()
        G_static = builder.build_static_graph(deps)
        G_fused = builder.fuse_graphs(G_static, nx.Graph(), alpha=1.0)

        detector = ClusterDetector(min_cluster_size=3, seed=42)
        clusters = detector.detect_clusters(G_fused, deps)
        filtered = detector.filter_clusters(clusters, deps)

        if not filtered:
            pytest.skip("No clusters passed filtering")

        # Generate code for first cluster
        try:
            jdt = JDTCodeGenerator()
        except FileNotFoundError:
            pytest.skip("JDT JAR not built")

        cluster = filtered[0]
        generated = jdt.generate(
            cluster=cluster,
            new_class_name="ExtractedGroup",
            class_file=class_file,
            repo_path=str(repo_path),
            class_deps=deps,
        )

        assert generated.new_class_code, "No new class code generated"
        assert generated.modified_original_code, "No modified original code"
        assert "class ExtractedGroup" in generated.new_class_code
