"""
Performance benchmarks for GenEC pipeline.

Measures execution time for key operations and tracks performance regressions.
Run with: pytest tests/benchmarks/ -v
"""

import time
from pathlib import Path
from typing import Dict, Any

import pytest

from genec.core.dependency_analyzer import DependencyAnalyzer
from genec.core.graph_builder import GraphBuilder
from genec.core.cluster_detector import ClusterDetector
from genec.config import GenECConfig


class TestPerformanceBenchmarks:
    """Performance benchmarks for core components."""

    @pytest.fixture
    def sample_java_code(self) -> str:
        """Generate a moderately complex Java class for testing."""
        return """
public class SampleClass {
    private int field1;
    private String field2;
    private double field3;
    private boolean field4;

    public void method1() {
        field1++;
        method2();
    }

    public void method2() {
        field2 = "test";
        method3();
    }

    public void method3() {
        field3 = 3.14;
        method4();
    }

    public void method4() {
        field4 = true;
    }

    public int getField1() {
        return field1;
    }

    public void setField1(int value) {
        this.field1 = value;
    }

    public String getField2() {
        return field2;
    }

    public void setField2(String value) {
        this.field2 = value;
    }

    public double calculate() {
        method1();
        method2();
        return field1 + field3;
    }

    public boolean validate() {
        method3();
        method4();
        return field4;
    }
}
"""

    @pytest.fixture
    def java_file(self, sample_java_code: str, tmp_path: Path) -> Path:
        """Create a temporary Java file."""
        java_file = tmp_path / "SampleClass.java"
        java_file.write_text(sample_java_code)
        return java_file

    def test_benchmark_dependency_analysis(self, java_file: Path, tmp_path: Path):
        """Benchmark dependency analysis performance."""
        analyzer = DependencyAnalyzer()

        start_time = time.time()
        class_deps = analyzer.analyze_class(str(java_file))
        duration = time.time() - start_time

        # Should complete in under 2 seconds for this simple class
        assert duration < 2.0, f"Dependency analysis took {duration:.2f}s (expected < 2s)"
        assert class_deps is not None
        assert len(class_deps.methods) > 0

        print(f"\n✓ Dependency analysis: {duration:.3f}s")

    def test_benchmark_graph_building(self, java_file: Path, tmp_path: Path):
        """Benchmark graph construction performance."""
        analyzer = DependencyAnalyzer()
        class_deps = analyzer.analyze_class(str(java_file))

        builder = GraphBuilder()

        start_time = time.time()
        G_static = builder.build_static_graph(class_deps)
        duration = time.time() - start_time

        # Graph building should be very fast
        assert duration < 0.5, f"Graph building took {duration:.2f}s (expected < 0.5s)"
        assert G_static.number_of_nodes() > 0

        print(f"\n✓ Graph building: {duration:.3f}s")

    def test_benchmark_cluster_detection(self, java_file: Path, tmp_path: Path):
        """Benchmark cluster detection performance."""
        # Setup
        analyzer = DependencyAnalyzer()
        class_deps = analyzer.analyze_class(str(java_file))

        builder = GraphBuilder()
        G_static = builder.build_static_graph(class_deps)

        detector = ClusterDetector()

        start_time = time.time()
        clusters = detector.detect_clusters(G_static)
        duration = time.time() - start_time

        # Cluster detection should be fast for small graphs
        assert duration < 1.0, f"Cluster detection took {duration:.2f}s (expected < 1s)"
        assert len(clusters) >= 0

        print(f"\n✓ Cluster detection: {duration:.3f}s ({len(clusters)} clusters)")

    def test_benchmark_config_loading(self):
        """Benchmark configuration loading with Pydantic."""
        start_time = time.time()
        config = GenECConfig()  # Load with defaults
        duration = time.time() - start_time

        # Config loading should be instant
        assert duration < 0.1, f"Config loading took {duration:.2f}s (expected < 0.1s)"
        assert config.fusion.alpha == 0.5

        print(f"\n✓ Config loading: {duration:.3f}s")

    def test_benchmark_full_analysis_pipeline(self, java_file: Path, tmp_path: Path):
        """Benchmark complete analysis pipeline (no LLM)."""
        start_time = time.time()

        # 1. Dependency Analysis
        analyzer = DependencyAnalyzer()
        class_deps = analyzer.analyze_class(str(java_file))

        # 2. Graph Building
        builder = GraphBuilder()
        G_static = builder.build_static_graph(class_deps)

        # 3. Cluster Detection
        detector = ClusterDetector()
        clusters = detector.detect_clusters(G_static)
        filtered = detector.filter_clusters(clusters)
        ranked = detector.rank_clusters(filtered)

        duration = time.time() - start_time

        # Full pipeline should complete quickly for simple class
        assert duration < 3.0, f"Full pipeline took {duration:.2f}s (expected < 3s)"

        print(f"\n✓ Full analysis pipeline: {duration:.3f}s")
        print(f"  - {len(class_deps.methods)} methods analyzed")
        print(f"  - {G_static.number_of_nodes()} nodes in graph")
        print(f"  - {len(clusters)} clusters detected")
        print(f"  - {len(ranked)} clusters after filtering/ranking")


class TestScalabilityBenchmarks:
    """Scalability benchmarks with varying input sizes."""

    def generate_large_class(self, num_methods: int) -> str:
        """Generate a Java class with specified number of methods."""
        fields = "\n    ".join([f"private int field{i};" for i in range(num_methods // 2)])

        methods = []
        for i in range(num_methods):
            method = f"""
    public void method{i}() {{
        field{i % (num_methods // 2)}++;
        {f"method{(i+1) % num_methods}();" if i < num_methods - 1 else ""}
    }}"""
            methods.append(method)

        return f"""
public class LargeClass {{
    {fields}

    {''.join(methods)}
}}
"""

    @pytest.mark.parametrize("num_methods", [10, 20, 50])
    def test_scalability_by_class_size(self, num_methods: int, tmp_path: Path):
        """Test performance scaling with class size."""
        java_code = self.generate_large_class(num_methods)
        java_file = tmp_path / f"LargeClass_{num_methods}.java"
        java_file.write_text(java_code)

        analyzer = DependencyAnalyzer()

        start_time = time.time()
        class_deps = analyzer.analyze_class(str(java_file))
        duration = time.time() - start_time

        # Performance should scale roughly linearly
        expected_max = num_methods * 0.05  # 50ms per method
        assert duration < expected_max, \
            f"Analysis of {num_methods} methods took {duration:.2f}s (expected < {expected_max:.2f}s)"

        print(f"\n✓ {num_methods} methods: {duration:.3f}s ({duration/num_methods*1000:.1f}ms/method)")


def generate_performance_report(results: Dict[str, Any]) -> str:
    """Generate a performance report from benchmark results."""
    report = []
    report.append("# GenEC Performance Benchmark Report\n")
    report.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    report.append("\n## Results\n")

    for test_name, metrics in results.items():
        report.append(f"\n### {test_name}")
        report.append(f"- Duration: {metrics['duration']:.3f}s")
        if 'throughput' in metrics:
            report.append(f"- Throughput: {metrics['throughput']:.1f} items/s")

    return "\n".join(report)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
