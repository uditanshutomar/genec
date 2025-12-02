#!/usr/bin/env python3
"""
Test suite for Stage 3 (Graph Fusion) improvements.

Tests the following enhancements:
1. Adaptive fusion using hotspot data
2. Centrality metrics calculation
3. Graph export capabilities
"""

import sys
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from genec.core.graph_builder import GraphBuilder
from genec.core.dependency_analyzer import ClassDependencies, MethodInfo
from genec.core.evolutionary_miner import EvolutionaryData
import networkx as nx


def test_adaptive_fusion():
    """Test adaptive fusion with hotspot data."""
    print("\n" + "=" * 70)
    print("TEST 1: Adaptive Fusion with Hotspot Data")
    print("=" * 70)

    builder = GraphBuilder()

    # Create simple static graph
    G_static = nx.Graph()
    G_static.add_node('method1', type='method')
    G_static.add_node('method2', type='method')
    G_static.add_node('method3', type='method')
    G_static.add_edge('method1', 'method2', weight=0.8)
    G_static.add_edge('method2', 'method3', weight=0.6)

    # Create simple evolutionary graph
    G_evo = nx.Graph()
    G_evo.add_node('method1', type='method')
    G_evo.add_node('method2', type='method')
    G_evo.add_node('method3', type='method')
    G_evo.add_edge('method1', 'method2', weight=0.5)
    G_evo.add_edge('method1', 'method3', weight=0.7)

    # Test without adaptive fusion
    print("\nTest 1a: Regular fusion (alpha=0.5)")
    G_fused_regular = builder.fuse_graphs(
        G_static, G_evo,
        alpha=0.5,
        edge_threshold=0.1,
        adaptive_fusion=False
    )

    print(f"  Nodes: {G_fused_regular.number_of_nodes()}")
    print(f"  Edges: {G_fused_regular.number_of_edges()}")

    for u, v, data in G_fused_regular.edges(data=True):
        print(f"  Edge {u} <-> {v}: weight={data['weight']:.3f}, alpha={data.get('alpha', 0.5):.2f}")

    # Test with adaptive fusion
    print("\nTest 1b: Adaptive fusion with hotspot data")

    hotspot_data = [
        {'method': 'method1', 'hotspot_score': 0.9},  # High hotspot (more evolutionary weight)
        {'method': 'method2', 'hotspot_score': 0.3},  # Low hotspot (more static weight)
        {'method': 'method3', 'hotspot_score': 0.1},  # Very low hotspot (most static weight)
    ]

    G_fused_adaptive = builder.fuse_graphs(
        G_static, G_evo,
        alpha=0.5,
        edge_threshold=0.1,
        hotspot_data=hotspot_data,
        adaptive_fusion=True
    )

    print(f"  Nodes: {G_fused_adaptive.number_of_nodes()}")
    print(f"  Edges: {G_fused_adaptive.number_of_edges()}")

    for u, v, data in G_fused_adaptive.edges(data=True):
        print(f"  Edge {u} <-> {v}: weight={data['weight']:.3f}, alpha={data.get('alpha', 0.5):.2f}")

    # Verify adaptive fusion adjusts alpha
    print("\nTest 1c: Verify adaptive alpha adjustment")
    found_high_hotspot_edge = False
    for u, v, data in G_fused_adaptive.edges(data=True):
        edge_alpha = data.get('alpha', 0.5)
        # Check edges involving method1 (high hotspot) and method2 (low hotspot)
        if (u == 'method1' and v == 'method2') or (u == 'method2' and v == 'method1'):
            # method1 has high hotspot (0.9), method2 has low (0.3)
            # Average = 0.6, expected alpha = 0.8 - 0.6*0.6 = 0.44
            expected_alpha = 0.8 - (0.6 * 0.6)
            assert abs(edge_alpha - expected_alpha) < 0.01, \
                f"Expected alpha ~{expected_alpha:.2f} for medium hotspot edge, got {edge_alpha:.2f}"
            print(f"  ✓ Medium hotspot edge {u}<->{v} has alpha: {edge_alpha:.2f} (expected ~{expected_alpha:.2f})")
            found_high_hotspot_edge = True
        elif (u == 'method2' and v == 'method3') or (u == 'method3' and v == 'method2'):
            # method2 has low hotspot (0.3), method3 has very low (0.1)
            # Average = 0.2, expected alpha = 0.8 - 0.6*0.2 = 0.68
            expected_alpha = 0.8 - (0.6 * 0.2)
            assert abs(edge_alpha - expected_alpha) < 0.01, \
                f"Expected alpha ~{expected_alpha:.2f} for low hotspot edge, got {edge_alpha:.2f}"
            print(f"  ✓ Low hotspot edge {u}<->{v} has high alpha: {edge_alpha:.2f} (expected ~{expected_alpha:.2f})")

    assert found_high_hotspot_edge, "Did not find method1-method2 edge to verify"

    print("\n✅ PASS: Adaptive fusion test")


def test_centrality_metrics():
    """Test centrality metrics calculation."""
    print("\n" + "=" * 70)
    print("TEST 2: Centrality Metrics")
    print("=" * 70)

    builder = GraphBuilder()

    # Create a more complex graph with clear centrality structure
    G = nx.Graph()

    # Hub node (high degree)
    G.add_node('hub', type='method')
    for i in range(1, 6):
        G.add_node(f'node{i}', type='method')
        G.add_edge('hub', f'node{i}', weight=0.5)

    # Bridge node (high betweenness)
    G.add_node('bridge', type='method')
    G.add_node('cluster1', type='method')
    G.add_node('cluster2', type='method')
    G.add_edge('hub', 'bridge', weight=0.8)
    G.add_edge('bridge', 'cluster1', weight=0.7)
    G.add_edge('bridge', 'cluster2', weight=0.7)

    print(f"\nGraph structure:")
    print(f"  Nodes: {G.number_of_nodes()}")
    print(f"  Edges: {G.number_of_edges()}")

    # Calculate centrality metrics
    print("\nTest 2a: Calculate centrality metrics")
    metrics = builder.calculate_centrality_metrics(G, top_n=5)

    print(f"\n  Calculated {len(metrics)} centrality metrics:")
    for metric_name in metrics:
        print(f"    - {metric_name}")

    # Check that all expected metrics are present
    expected_metrics = ['degree_centrality', 'betweenness_centrality', 'eigenvector_centrality', 'pagerank']
    for metric in expected_metrics:
        assert metric in metrics, f"Missing metric: {metric}"
        print(f"  ✓ Metric {metric} calculated")

    # Display top nodes for each metric
    print("\nTest 2b: Top nodes per metric")
    for metric_name, node_scores in metrics.items():
        print(f"\n  {metric_name}:")
        for node, score in list(node_scores.items())[:3]:
            print(f"    {node}: {score:.4f}")

    # Verify hub has high degree centrality
    print("\nTest 2c: Verify hub has high degree centrality")
    hub_degree = metrics['degree_centrality'].get('hub', 0.0)
    print(f"  Hub degree centrality: {hub_degree:.4f}")
    assert hub_degree > 0.5, f"Expected hub to have high degree centrality, got {hub_degree}"
    print("  ✓ Hub has high degree centrality")

    # Test adding centrality to graph
    print("\nTest 2d: Add centrality as node attributes")
    G_with_centrality = builder.add_centrality_to_graph(G, metrics)

    # Verify attributes are added
    for node in G_with_centrality.nodes():
        node_data = G_with_centrality.nodes[node]
        for metric in expected_metrics:
            assert metric in node_data, f"Missing {metric} attribute for node {node}"

    print(f"  ✓ All centrality metrics added to {G_with_centrality.number_of_nodes()} nodes")

    print("\n✅ PASS: Centrality metrics test")


def test_graph_export():
    """Test graph export to various formats."""
    print("\n" + "=" * 70)
    print("TEST 3: Graph Export Capabilities")
    print("=" * 70)

    builder = GraphBuilder()

    # Create a simple test graph
    G = nx.Graph()
    G.add_node('method1', type='method')
    G.add_node('method2', type='method')
    G.add_node('field1', type='field')
    G.add_edge('method1', 'method2', weight=0.8, static_weight=0.6, evo_weight=0.4)
    G.add_edge('method1', 'field1', weight=0.5, static_weight=0.5, evo_weight=0.0)

    print(f"\nTest graph:")
    print(f"  Nodes: {G.number_of_nodes()}")
    print(f"  Edges: {G.number_of_edges()}")

    # Test export to different formats
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        formats = ['graphml', 'gml', 'json', 'csv', 'adjlist']

        print(f"\nTest 3a: Export to {len(formats)} formats")
        for fmt in formats:
            output_file = tmpdir / f"test_graph.{fmt}"

            try:
                builder.export_graph(G, str(output_file), format=fmt)

                # Verify file was created
                assert output_file.exists(), f"Export file not created: {output_file}"

                # Verify file has content
                file_size = output_file.stat().st_size
                assert file_size > 0, f"Export file is empty: {output_file}"

                actual_fmt = output_file.suffix[1:] if output_file.suffix else fmt
                print(f"  ✓ {fmt} ({actual_fmt}): {file_size} bytes")

            except Exception as e:
                # DOT format might fail if pydot is not installed
                if fmt == 'dot':
                    print(f"  ⚠ {fmt}: {e} (optional dependency)")
                else:
                    raise

        # Test centrality export
        print("\nTest 3b: Export centrality metrics")

        centrality_metrics = {
            'degree_centrality': {'method1': 0.8, 'method2': 0.6},
            'betweenness_centrality': {'method1': 0.5, 'method2': 0.3},
        }

        # Export as JSON
        json_file = tmpdir / "centrality.json"
        builder.export_centrality_metrics(centrality_metrics, str(json_file), format='json')
        assert json_file.exists(), "JSON export failed"
        print(f"  ✓ JSON: {json_file.stat().st_size} bytes")

        # Export as CSV
        csv_file = tmpdir / "centrality.csv"
        builder.export_centrality_metrics(centrality_metrics, str(csv_file), format='csv')
        assert csv_file.exists(), "CSV export failed"
        print(f"  ✓ CSV: {csv_file.stat().st_size} bytes")

        # Verify CSV content
        with open(csv_file) as f:
            lines = f.readlines()
            print(f"\n  CSV preview:")
            for line in lines[:5]:
                print(f"    {line.strip()}")

    print("\n✅ PASS: Graph export test")


def test_integration():
    """Integration test with all Stage 3 features."""
    print("\n" + "=" * 70)
    print("TEST 4: Integration Test (All Stage 3 Features)")
    print("=" * 70)

    builder = GraphBuilder()

    # Create realistic static graph
    G_static = nx.Graph()
    methods = ['processPayment(Order)', 'validateOrder(Order)', 'calculateTotal(Order)',
               'sendConfirmation(Order)', 'logTransaction(Order)']

    for method in methods:
        G_static.add_node(method, type='method')

    # Add static dependencies
    G_static.add_edge('processPayment(Order)', 'validateOrder(Order)', weight=0.9)
    G_static.add_edge('processPayment(Order)', 'calculateTotal(Order)', weight=0.8)
    G_static.add_edge('processPayment(Order)', 'sendConfirmation(Order)', weight=0.7)
    G_static.add_edge('processPayment(Order)', 'logTransaction(Order)', weight=0.5)

    # Create evolutionary graph
    G_evo = nx.Graph()
    for method in methods:
        G_evo.add_node(method, type='method')

    # Add evolutionary coupling
    G_evo.add_edge('processPayment(Order)', 'validateOrder(Order)', weight=0.6)
    G_evo.add_edge('validateOrder(Order)', 'calculateTotal(Order)', weight=0.7)
    G_evo.add_edge('sendConfirmation(Order)', 'logTransaction(Order)', weight=0.5)

    print("\nTest 4a: Static graph")
    print(f"  Nodes: {G_static.number_of_nodes()}")
    print(f"  Edges: {G_static.number_of_edges()}")

    print("\nTest 4b: Evolutionary graph")
    print(f"  Nodes: {G_evo.number_of_nodes()}")
    print(f"  Edges: {G_evo.number_of_edges()}")

    # Create hotspot data
    hotspot_data = [
        {'method': 'processPayment(Order)', 'hotspot_score': 0.9},
        {'method': 'validateOrder(Order)', 'hotspot_score': 0.7},
        {'method': 'calculateTotal(Order)', 'hotspot_score': 0.3},
        {'method': 'sendConfirmation(Order)', 'hotspot_score': 0.2},
        {'method': 'logTransaction(Order)', 'hotspot_score': 0.1},
    ]

    # Fuse with adaptive fusion
    print("\nTest 4c: Fuse graphs with adaptive fusion")
    G_fused = builder.fuse_graphs(
        G_static, G_evo,
        alpha=0.5,
        edge_threshold=0.1,
        hotspot_data=hotspot_data,
        adaptive_fusion=True
    )

    print(f"  Fused nodes: {G_fused.number_of_nodes()}")
    print(f"  Fused edges: {G_fused.number_of_edges()}")

    # Calculate centrality
    print("\nTest 4d: Calculate centrality metrics")
    centrality_metrics = builder.calculate_centrality_metrics(G_fused, top_n=5)

    print(f"  Calculated {len(centrality_metrics)} metrics")
    print("\n  Top 3 by PageRank:")
    for node, score in list(centrality_metrics['pagerank'].items())[:3]:
        print(f"    {node}: {score:.4f}")

    # Add centrality to graph
    G_fused = builder.add_centrality_to_graph(G_fused, centrality_metrics)

    # Export results
    print("\nTest 4e: Export results")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Export graph
        graph_file = tmpdir / "payment_processor_fused.graphml"
        builder.export_graph(G_fused, str(graph_file), format='graphml')
        print(f"  ✓ Graph exported: {graph_file.stat().st_size} bytes")

        # Export centrality
        centrality_file = tmpdir / "payment_processor_centrality.json"
        builder.export_centrality_metrics(centrality_metrics, str(centrality_file), format='json')
        print(f"  ✓ Centrality exported: {centrality_file.stat().st_size} bytes")

    # Get graph metrics
    print("\nTest 4f: Calculate graph metrics")
    metrics = builder.get_graph_metrics(G_fused)

    print("  Graph metrics:")
    for key, value in metrics.items():
        print(f"    {key}: {value:.4f}" if isinstance(value, float) else f"    {key}: {value}")

    print("\n✅ PASS: Integration test")


def main():
    """Run all Stage 3 enhancement tests."""
    print("=" * 70)
    print("STAGE 3 (Graph Fusion) Enhancement Tests")
    print("=" * 70)
    print("\nTesting 3 enhancements:")
    print("  1. Adaptive fusion with hotspot data")
    print("  2. Centrality metrics (degree, betweenness, eigenvector, PageRank)")
    print("  3. Graph export (GraphML, GML, DOT, JSON, CSV)")

    tests = [
        ("Adaptive Fusion", test_adaptive_fusion),
        ("Centrality Metrics", test_centrality_metrics),
        ("Graph Export", test_graph_export),
        ("Integration Test", test_integration),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ FAIL: {test_name}")
            print(f"  Error: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ ERROR: {test_name}")
            print(f"  Exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")

    if failed == 0:
        print("\n🎉 All Stage 3 tests PASSED!")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
