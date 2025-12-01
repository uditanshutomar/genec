"""Integration test for Louvain process isolation fix.

This test verifies that Louvain clustering works correctly when called
from within a ThreadPoolExecutor context, which previously caused hangs.
"""
import concurrent.futures
import networkx as nx
import pytest

from genec.core.cluster_detector import ClusterDetector


def test_louvain_with_threadpool():
    """Verify Louvain works when called from ThreadPoolExecutor."""

    # Create a test graph
    G = nx.karate_club_graph()  # Classic test graph with 34 nodes
    for u, v in G.edges():
        G[u][v]['weight'] = 1.0

    detector = ClusterDetector(
        min_cluster_size=2,
        max_cluster_size=20,
        min_cohesion=0.1
    )

    def run_detection():
        """Run detection in worker thread."""
        return detector.detect_clusters(G)

    # This previously would hang indefinitely
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future = executor.submit(run_detection)
        result = future.result(timeout=60)  # Should complete well before 60s

    # Verify we got clusters
    assert result is not None, "Detection returned None"
    assert len(result) > 0, "No clusters detected"
    assert all(len(cluster) > 0 for cluster in result), "Empty cluster found"

    print(f"✓ Detected {len(result)} clusters from ThreadPoolExecutor")


def test_louvain_timeout():
    """Verify Louvain times out gracefully on complex graphs."""

    # Create a very large, dense graph that might timeout
    G = nx.complete_graph(200)  # 200 nodes, all connected
    for u, v in G.edges():
        G[u][v]['weight'] = 1.0

    detector = ClusterDetector()

    # Override timeout to very short value for testing
    partition = detector._run_louvain_isolated(G, timeout=1)

    # Should either complete or return None (timeout)
    # Both are acceptable - we just verify no hang
    if partition is None:
        print("✓ Louvain timed out gracefully (expected)")
    else:
        print(f"✓ Louvain completed quickly, found {len(set(partition.values()))} communities")


def test_louvain_direct_call():
    """Verify normal Louvain still works (without ThreadPoolExecutor)."""

    G = nx.karate_club_graph()
    for u, v in G.edges():
        G[u][v]['weight'] = 1.0

    detector = ClusterDetector(
        min_cluster_size=2,
        max_cluster_size=20,
        min_cohesion=0.1
    )

    result = detector.detect_clusters(G)

    assert result is not None
    assert len(result) > 0
    print(f"✓ Normal detection works, found {len(result)} clusters")


if __name__ == '__main__':
    print("Running Louvain process isolation tests...")
    print()

    print("Test 1: Direct call (baseline)")
    test_louvain_direct_call()
    print()

    print("Test 2: With ThreadPoolExecutor (hang test)")
    test_louvain_with_threadpool()
    print()

    print("Test 3: Timeout handling")
    test_louvain_timeout()
    print()

    print("✓ All tests passed!")
