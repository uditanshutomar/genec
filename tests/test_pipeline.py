"""Tests for GenEC pipeline."""

import pytest
import tempfile
from pathlib import Path

from genec.core.dependency_analyzer import DependencyAnalyzer
from genec.core.graph_builder import GraphBuilder
from genec.core.cluster_detector import ClusterDetector
from genec.metrics.cohesion_calculator import CohesionCalculator
from genec.metrics.coupling_calculator import CouplingCalculator


# Sample Java class for testing
SAMPLE_JAVA_CLASS = """
package com.example;

public class GodClass {
    private String name;
    private int age;
    private String address;
    private String phoneNumber;

    private double accountBalance;
    private String accountNumber;

    public GodClass(String name, int age) {
        this.name = name;
        this.age = age;
    }

    // Person-related methods
    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public int getAge() {
        return age;
    }

    public void setAge(int age) {
        this.age = age;
    }

    public String getAddress() {
        return address;
    }

    public void setAddress(String address) {
        this.address = address;
    }

    public String getPhoneNumber() {
        return phoneNumber;
    }

    public void setPhoneNumber(String phoneNumber) {
        this.phoneNumber = phoneNumber;
    }

    // Account-related methods
    public double getAccountBalance() {
        return accountBalance;
    }

    public void deposit(double amount) {
        accountBalance += amount;
    }

    public void withdraw(double amount) {
        if (accountBalance >= amount) {
            accountBalance -= amount;
        }
    }

    public String getAccountNumber() {
        return accountNumber;
    }

    public void setAccountNumber(String accountNumber) {
        this.accountNumber = accountNumber;
    }
}
"""


class TestDependencyAnalyzer:
    """Test dependency analyzer."""

    def test_analyze_class(self, tmp_path):
        """Test analyzing a Java class."""
        # Create temp Java file
        java_file = tmp_path / "GodClass.java"
        java_file.write_text(SAMPLE_JAVA_CLASS)

        # Analyze
        analyzer = DependencyAnalyzer()
        class_deps = analyzer.analyze_class(str(java_file))

        # Assertions
        assert class_deps is not None
        assert class_deps.class_name == "GodClass"
        assert class_deps.package_name == "com.example"
        assert len(class_deps.fields) == 6
        assert len(class_deps.get_all_methods()) > 0
        assert class_deps.dependency_matrix is not None

    def test_dependency_matrix_shape(self, tmp_path):
        """Test dependency matrix has correct shape."""
        java_file = tmp_path / "GodClass.java"
        java_file.write_text(SAMPLE_JAVA_CLASS)

        analyzer = DependencyAnalyzer()
        class_deps = analyzer.analyze_class(str(java_file))

        n_members = len(class_deps.member_names)
        assert class_deps.dependency_matrix.shape == (n_members, n_members)


class TestGraphBuilder:
    """Test graph builder."""

    def test_build_static_graph(self, tmp_path):
        """Test building static dependency graph."""
        java_file = tmp_path / "GodClass.java"
        java_file.write_text(SAMPLE_JAVA_CLASS)

        analyzer = DependencyAnalyzer()
        class_deps = analyzer.analyze_class(str(java_file))

        builder = GraphBuilder()
        graph = builder.build_static_graph(class_deps)

        assert graph is not None
        assert graph.number_of_nodes() == len(class_deps.member_names)

    def test_graph_metrics(self, tmp_path):
        """Test graph metrics calculation."""
        java_file = tmp_path / "GodClass.java"
        java_file.write_text(SAMPLE_JAVA_CLASS)

        analyzer = DependencyAnalyzer()
        class_deps = analyzer.analyze_class(str(java_file))

        builder = GraphBuilder()
        graph = builder.build_static_graph(class_deps)

        metrics = builder.get_graph_metrics(graph)

        assert 'num_nodes' in metrics
        assert 'num_edges' in metrics
        assert 'density' in metrics
        assert metrics['num_nodes'] > 0


class TestClusterDetector:
    """Test cluster detector."""

    def test_detect_clusters(self, tmp_path):
        """Test cluster detection."""
        java_file = tmp_path / "GodClass.java"
        java_file.write_text(SAMPLE_JAVA_CLASS)

        analyzer = DependencyAnalyzer()
        class_deps = analyzer.analyze_class(str(java_file))

        builder = GraphBuilder()
        graph = builder.build_static_graph(class_deps)

        detector = ClusterDetector(min_cluster_size=2, max_cluster_size=20)
        clusters = detector.detect_clusters(graph)

        assert clusters is not None
        assert len(clusters) > 0

    def test_filter_clusters(self, tmp_path):
        """Test cluster filtering."""
        java_file = tmp_path / "GodClass.java"
        java_file.write_text(SAMPLE_JAVA_CLASS)

        analyzer = DependencyAnalyzer()
        class_deps = analyzer.analyze_class(str(java_file))

        builder = GraphBuilder()
        graph = builder.build_static_graph(class_deps)

        detector = ClusterDetector(min_cluster_size=2, max_cluster_size=10)
        clusters = detector.detect_clusters(graph)
        filtered = detector.filter_clusters(clusters)

        # All filtered clusters should meet size constraints
        for cluster in filtered:
            assert len(cluster) >= detector.min_cluster_size
            assert len(cluster) <= detector.max_cluster_size


class TestCohesionCalculator:
    """Test cohesion calculator."""

    def test_calculate_lcom5(self, tmp_path):
        """Test LCOM5 calculation."""
        java_file = tmp_path / "GodClass.java"
        java_file.write_text(SAMPLE_JAVA_CLASS)

        analyzer = DependencyAnalyzer()
        class_deps = analyzer.analyze_class(str(java_file))

        calculator = CohesionCalculator()
        lcom5 = calculator.calculate_lcom5(class_deps)

        assert lcom5 >= 0.0
        assert lcom5 <= 1.0

    def test_calculate_tcc(self, tmp_path):
        """Test TCC calculation."""
        java_file = tmp_path / "GodClass.java"
        java_file.write_text(SAMPLE_JAVA_CLASS)

        analyzer = DependencyAnalyzer()
        class_deps = analyzer.analyze_class(str(java_file))

        calculator = CohesionCalculator()
        tcc = calculator.calculate_tcc(class_deps)

        assert tcc >= 0.0
        assert tcc <= 1.0


class TestCouplingCalculator:
    """Test coupling calculator."""

    def test_calculate_cbo(self, tmp_path):
        """Test CBO calculation."""
        java_file = tmp_path / "GodClass.java"
        java_file.write_text(SAMPLE_JAVA_CLASS)

        analyzer = DependencyAnalyzer()
        class_deps = analyzer.analyze_class(str(java_file))

        calculator = CouplingCalculator()
        cbo = calculator.calculate_cbo(class_deps)

        assert cbo >= 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
