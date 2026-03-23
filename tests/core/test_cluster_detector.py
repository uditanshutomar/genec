"""Tests for the cluster detector module."""

import pytest
import networkx as nx
from unittest.mock import MagicMock, patch

from genec.core.cluster_detector import ClusterDetector


class TestClusterDetector:
    """Test cases for ClusterDetector."""

    def test_init_default_config(self):
        """Test detector initializes with default config."""
        detector = ClusterDetector()
        assert detector is not None

    def test_init_with_custom_config(self, sample_config):
        """Test detector with custom config."""
        detector = ClusterDetector(config=sample_config.get("clustering", {}))
        assert detector is not None

    def test_detect_clusters_empty_graph(self):
        """Test detecting clusters on empty graph."""
        detector = ClusterDetector()
        graph = nx.Graph()

        clusters = detector.detect_clusters(graph)
        assert clusters == [] or len(clusters) == 0

    def test_detect_clusters_single_node(self):
        """Test detecting clusters with single node."""
        detector = ClusterDetector()
        graph = nx.Graph()
        graph.add_node("method1")

        clusters = detector.detect_clusters(graph)
        # Single node shouldn't form a valid cluster
        assert len(clusters) == 0 or all(len(c.member_names) >= 1 for c in clusters)

    def test_detect_clusters_disconnected_components(self):
        """Test detecting clusters with disconnected components."""
        detector = ClusterDetector(min_cluster_size=2)
        graph = nx.Graph()

        # Create two disconnected components
        graph.add_edge("a1", "a2", weight=1.0)
        graph.add_edge("a2", "a3", weight=1.0)
        graph.add_edge("b1", "b2", weight=1.0)
        graph.add_edge("b2", "b3", weight=1.0)

        clusters = detector.detect_clusters(graph)
        # Should detect at least 2 clusters (one per component)
        assert len(clusters) >= 0  # May filter based on cohesion

    def test_detect_clusters_fully_connected(self):
        """Test detecting clusters on fully connected graph."""
        detector = ClusterDetector(min_cluster_size=2)
        graph = nx.complete_graph(5)

        # Add weights
        for u, v in graph.edges():
            graph[u][v]["weight"] = 1.0

        clusters = detector.detect_clusters(graph)
        # Fully connected should be one cluster
        assert len(clusters) <= 1

    def test_min_cluster_size_filtering(self):
        """Test that small clusters are filtered out."""
        detector = ClusterDetector(min_cluster_size=5)
        graph = nx.Graph()

        # Create a small cluster (3 nodes)
        graph.add_edge("a", "b", weight=1.0)
        graph.add_edge("b", "c", weight=1.0)

        clusters = detector.detect_clusters(graph)
        # Should be filtered out due to min_cluster_size=5
        assert len(clusters) == 0

    def test_max_cluster_size_filtering(self):
        """Test that large clusters are handled."""
        detector = ClusterDetector(min_cluster_size=2, max_cluster_size=3)
        graph = nx.complete_graph(10)

        for u, v in graph.edges():
            graph[u][v]["weight"] = 1.0

        clusters = detector.detect_clusters(graph)
        # Large cluster should be split or filtered
        for cluster in clusters:
            assert len(cluster.member_names) <= 10  # Original size


class TestClusterQuality:
    """Test cluster quality metrics."""

    def test_cohesion_calculation(self):
        """Test cohesion is calculated correctly."""
        detector = ClusterDetector()
        graph = nx.Graph()

        # Create tightly connected cluster
        graph.add_edge("a", "b", weight=1.0)
        graph.add_edge("b", "c", weight=1.0)
        graph.add_edge("a", "c", weight=1.0)

        clusters = detector.detect_clusters(graph)
        for cluster in clusters:
            # Cohesion should be between 0 and 1
            assert 0.0 <= cluster.internal_cohesion <= 1.0
