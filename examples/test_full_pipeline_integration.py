#!/usr/bin/env python3
"""
Full Pipeline Integration Test: Stage 1 → Stage 2 → Stage 3

Tests the complete integration from static analysis through evolutionary
coupling to graph fusion with all Stage 3 enhancements.
"""

import sys
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from genec.core.dependency_analyzer import DependencyAnalyzer
from genec.core.evolutionary_miner import EvolutionaryMiner
from genec.core.graph_builder import GraphBuilder


def test_stage1_to_stage2_integration():
    """Test Stage 1 (Static Analysis) → Stage 2 (Evolutionary Coupling) integration."""
    print("\n" + "=" * 70)
    print("TEST 1: Stage 1 → Stage 2 Integration")
    print("=" * 70)

    # Create test Java file
    with tempfile.TemporaryDirectory() as tmpdir:
        java_file = Path(tmpdir) / "TestClass.java"
        java_file.write_text("""
public class TestClass {
    private int count = 0;

    public void increment() {
        count++;
    }

    public void decrement() {
        count--;
    }

    public int getCount() {
        return count;
    }
}
        """)

        print("\nStage 1: Static Dependency Analysis")
        analyzer = DependencyAnalyzer()
        class_deps = analyzer.analyze_class(str(java_file))

        assert class_deps is not None, "Stage 1 failed: No class dependencies"
        assert class_deps.class_name == "TestClass"

        methods = class_deps.get_all_methods()
        print(f"  ✓ Analyzed class: {class_deps.class_name}")
        print(f"  ✓ Found {len(methods)} methods")

        for method in methods:
            print(f"    - {method.signature}")

        print("\nStage 2: Evolutionary Coupling (Mock)")
        # Note: Real git integration requires a git repo
        # This test verifies the data structures work together
        miner = EvolutionaryMiner()

        # Verify we can create method signatures from Stage 1
        method_signatures = {m.name: m.signature for m in methods}
        print(f"  ✓ Created method signature mapping: {len(method_signatures)} entries")

        for name, sig in method_signatures.items():
            print(f"    {name} → {sig}")

        print("\n✅ PASS: Stage 1 → Stage 2 integration")


def test_stage2_to_stage3_integration():
    """Test Stage 2 (Evolutionary Coupling) → Stage 3 (Graph Fusion) integration."""
    print("\n" + "=" * 70)
    print("TEST 2: Stage 2 → Stage 3 Integration")
    print("=" * 70)

    import networkx as nx
    from genec.core.evolutionary_miner import EvolutionaryData

    print("\nStage 2: Create mock evolutionary data")
    # Create mock evolutionary data
    evo_data = EvolutionaryData()
    evo_data.method_names = ["increment()", "decrement()", "getCount()"]
    evo_data.coupling_strengths = {
        ("increment()", "getCount()"): 0.7,
        ("decrement()", "getCount()"): 0.6,
    }
    evo_data.method_stats = {
        "increment()": {"total_commits": 10, "sum_coupling": 0.7},
        "decrement()": {"total_commits": 8, "sum_coupling": 0.6},
        "getCount()": {"total_commits": 12, "sum_coupling": 1.3},
    }

    print(f"  ✓ Methods: {len(evo_data.method_names)}")
    print(f"  ✓ Coupling pairs: {len(evo_data.coupling_strengths)}")

    print("\nStage 3: Build evolutionary graph")
    builder = GraphBuilder()

    # Test with method signatures
    method_signatures = {
        "increment": "increment()",
        "decrement": "decrement()",
        "getCount": "getCount()",
    }

    G_evo = builder.build_evolutionary_graph(evo_data, method_signatures)

    print(f"  ✓ Evolutionary graph: {G_evo.number_of_nodes()} nodes, {G_evo.number_of_edges()} edges")

    # Verify graph structure
    assert G_evo.number_of_nodes() == 3, f"Expected 3 nodes, got {G_evo.number_of_nodes()}"
    assert G_evo.number_of_edges() == 2, f"Expected 2 edges, got {G_evo.number_of_edges()}"

    print("\n✅ PASS: Stage 2 → Stage 3 integration")


def test_full_pipeline_integration():
    """Test full Stage 1 → Stage 2 → Stage 3 pipeline with all enhancements."""
    print("\n" + "=" * 70)
    print("TEST 3: Full Pipeline Integration (Stage 1 → 2 → 3)")
    print("=" * 70)

    import networkx as nx
    from genec.core.dependency_analyzer import ClassDependencies, MethodInfo
    from genec.core.evolutionary_miner import EvolutionaryData, EvolutionaryMiner

    # Stage 1: Static analysis (mock)
    print("\nStage 1: Static Dependency Analysis")
    class_deps = ClassDependencies(
        class_name="PaymentProcessor",
        package_name="com.example",
        file_path="/tmp/PaymentProcessor.java"
    )

    # Add methods
    method1 = MethodInfo(
        name="processPayment",
        signature="processPayment(Order)",
        return_type="void",
        modifiers=["public"],
        parameters=[{"type": "Order", "name": "order"}],
        start_line=10,
        end_line=15,
        body="validateOrder(order); calculateTotal(order);",
    )
    method2 = MethodInfo(
        name="validateOrder",
        signature="validateOrder(Order)",
        return_type="void",
        modifiers=["public"],
        parameters=[{"type": "Order", "name": "order"}],
        start_line=17,
        end_line=20,
        body="order.validate();",
    )
    method3 = MethodInfo(
        name="calculateTotal",
        signature="calculateTotal(Order)",
        return_type="double",
        modifiers=["public"],
        parameters=[{"type": "Order", "name": "order"}],
        start_line=22,
        end_line=25,
        body="return order.getTotal();",
    )

    class_deps.add_member(method1)
    class_deps.add_member(method2)
    class_deps.add_member(method3)

    # Set up dependencies
    class_deps.dependency_matrix[0][1] = 0.9  # processPayment → validateOrder
    class_deps.dependency_matrix[0][2] = 0.8  # processPayment → calculateTotal

    print(f"  ✓ Class: {class_deps.class_name}")
    print(f"  ✓ Methods: {len(class_deps.get_all_methods())}")

    # Stage 2: Evolutionary coupling (mock)
    print("\nStage 2: Evolutionary Coupling")
    evo_data = EvolutionaryData()
    evo_data.method_names = ["processPayment", "validateOrder", "calculateTotal"]
    evo_data.coupling_strengths = {
        ("processPayment", "validateOrder"): 0.6,
        ("processPayment", "calculateTotal"): 0.5,
    }
    evo_data.method_stats = {
        "processPayment": {"total_commits": 20, "sum_coupling": 1.1},
        "validateOrder": {"total_commits": 15, "sum_coupling": 0.6},
        "calculateTotal": {"total_commits": 10, "sum_coupling": 0.5},
    }

    print(f"  ✓ Coupling pairs: {len(evo_data.coupling_strengths)}")

    # Calculate hotspots
    miner = EvolutionaryMiner()
    hotspot_data = miner.get_method_hotspots(evo_data, top_n=3)
    print(f"  ✓ Hotspots calculated: {len(hotspot_data)}")

    # Stage 3: Graph fusion with all enhancements
    print("\nStage 3: Graph Fusion with Enhancements")
    builder = GraphBuilder()

    # Build static graph
    G_static = builder.build_static_graph(class_deps)
    print(f"  ✓ Static graph: {G_static.number_of_nodes()} nodes, {G_static.number_of_edges()} edges")

    # Build evolutionary graph
    method_map = {m.name: m.signature for m in class_deps.get_all_methods()}
    G_evo = builder.build_evolutionary_graph(evo_data, method_map)
    print(f"  ✓ Evolutionary graph: {G_evo.number_of_nodes()} nodes, {G_evo.number_of_edges()} edges")

    # Test Feature 1: Regular fusion
    print("\n  Feature 1: Regular Fusion")
    G_fused_regular = builder.fuse_graphs(
        G_static, G_evo, alpha=0.5, edge_threshold=0.1, adaptive_fusion=False
    )
    print(f"    ✓ Fused graph: {G_fused_regular.number_of_nodes()} nodes, {G_fused_regular.number_of_edges()} edges")

    # Test Feature 2: Adaptive fusion
    print("\n  Feature 2: Adaptive Fusion (Enhancement 5)")
    G_fused_adaptive = builder.fuse_graphs(
        G_static,
        G_evo,
        alpha=0.5,
        edge_threshold=0.1,
        hotspot_data=hotspot_data,
        adaptive_fusion=True,
    )
    print(f"    ✓ Adaptive fused graph: {G_fused_adaptive.number_of_edges()} edges")

    # Verify adaptive fusion adjusted alpha
    has_adaptive_alpha = False
    for u, v, data in G_fused_adaptive.edges(data=True):
        if "alpha" in data and data["alpha"] != 0.5:
            has_adaptive_alpha = True
            print(f"    ✓ Edge {u}<->{v}: alpha={data['alpha']:.2f} (adapted)")
            break

    assert has_adaptive_alpha, "Adaptive fusion did not adjust alpha"

    # Test Feature 3: Centrality metrics (Enhancement 2)
    print("\n  Feature 3: Centrality Metrics (Enhancement 2)")
    centrality = builder.calculate_centrality_metrics(G_fused_adaptive, top_n=3)

    print(f"    ✓ Calculated {len(centrality)} centrality metrics")
    for metric_name in centrality:
        print(f"      - {metric_name}")

    assert "degree_centrality" in centrality
    assert "betweenness_centrality" in centrality
    assert "eigenvector_centrality" in centrality
    assert "pagerank" in centrality

    # Find most important method
    most_important = list(centrality["pagerank"].keys())[0]
    print(f"    ✓ Most important method (PageRank): {most_important}")

    # Test Feature 4: Export (Enhancement 4)
    print("\n  Feature 4: Graph Export (Enhancement 4)")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Export graph in multiple formats
        formats_tested = []
        for fmt in ["json", "csv", "gml"]:
            try:
                output_file = tmpdir / f"payment_processor.{fmt}"
                builder.export_graph(G_fused_adaptive, str(output_file), format=fmt)

                if output_file.exists():
                    size = output_file.stat().st_size
                    print(f"    ✓ Exported {fmt}: {size} bytes")
                    formats_tested.append(fmt)
            except Exception as e:
                print(f"    ⚠ {fmt} export failed: {e}")

        assert len(formats_tested) >= 2, "At least 2 export formats should work"

        # Export centrality
        centrality_file = tmpdir / "centrality.json"
        builder.export_centrality_metrics(centrality, str(centrality_file), format="json")
        print(f"    ✓ Exported centrality metrics: {centrality_file.stat().st_size} bytes")

    print("\n✅ PASS: Full pipeline integration (Stage 1 → 2 → 3)")


def test_pipeline_error_handling():
    """Test pipeline error handling and fallbacks."""
    print("\n" + "=" * 70)
    print("TEST 4: Pipeline Error Handling")
    print("=" * 70)

    builder = GraphBuilder()

    # Test 1: Empty hotspot data warning
    print("\nTest 4a: Empty hotspot data with adaptive fusion")
    import networkx as nx

    G_static = nx.Graph()
    G_static.add_node("method1", type="method")
    G_static.add_node("method2", type="method")
    G_static.add_edge("method1", "method2", weight=0.8)

    G_evo = nx.Graph()
    G_evo.add_node("method1", type="method")
    G_evo.add_node("method2", type="method")
    G_evo.add_edge("method1", "method2", weight=0.5)

    # This should log a warning but not crash
    G_fused = builder.fuse_graphs(
        G_static, G_evo, alpha=0.5, edge_threshold=0.1, hotspot_data=None, adaptive_fusion=True
    )

    print(f"  ✓ Handled empty hotspot data gracefully")
    print(f"  ✓ Fused graph: {G_fused.number_of_nodes()} nodes, {G_fused.number_of_edges()} edges")

    # Test 2: Empty graphs
    print("\nTest 4b: Empty graph centrality")
    G_empty = nx.Graph()
    centrality = builder.calculate_centrality_metrics(G_empty)
    assert centrality == {}, "Empty graph should return empty centrality"
    print("  ✓ Handled empty graph gracefully")

    print("\n✅ PASS: Pipeline error handling")


def main():
    """Run all integration tests."""
    print("=" * 70)
    print("FULL PIPELINE INTEGRATION TESTS (Stage 1 → 2 → 3)")
    print("=" * 70)
    print("\nTesting complete integration:")
    print("  Stage 1: Static Dependency Analysis")
    print("  Stage 2: Evolutionary Coupling Mining")
    print("  Stage 3: Graph Fusion with Enhancements")

    tests = [
        ("Stage 1 → 2 Integration", test_stage1_to_stage2_integration),
        ("Stage 2 → 3 Integration", test_stage2_to_stage3_integration),
        ("Full Pipeline (1 → 2 → 3)", test_full_pipeline_integration),
        ("Pipeline Error Handling", test_pipeline_error_handling),
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
        print("\n🎉 All pipeline integration tests PASSED!")
        print("\n✅ Stage 1 → Stage 2 → Stage 3 pipeline fully integrated")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
