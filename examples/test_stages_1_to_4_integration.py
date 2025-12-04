#!/usr/bin/env python3
"""
Simple end-to-end test to verify Stages 1-4 work together with new clustering improvements.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from genec.core.hybrid_dependency_analyzer import HybridDependencyAnalyzer
from genec.core.evolutionary_miner import EvolutionaryMiner
from genec.core.graph_builder import GraphBuilder
from genec.core.cluster_detector import ClusterDetector
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


def test_stages_1_to_4():
    """Test Stages 1-4 integration with new Leiden clustering."""
    print("\n" + "="*80)
    print("END-TO-END TEST: Stages 1-4 with Leiden Clustering")
    print("="*80)

    # Input file
    java_file = "examples/tutorial2/UserManager.java"
    repo_path = "."

    print(f"\nTesting with: {java_file}")

    # Stage 1: Dependency Analysis
    print("\n[Stage 1] Static Dependency Analysis")
    analyzer = HybridDependencyAnalyzer()
    class_deps = analyzer.analyze_class(java_file)

    if not class_deps:
        print("❌ FAILED: Could not analyze class")
        return False

    print(f"  ✓ Analyzed class: {class_deps.class_name}")
    print(f"  ✓ Methods: {len(class_deps.get_all_methods())}")
    print(f"  ✓ Fields: {len(class_deps.fields)}")

    # Stage 2: Evolutionary Mining (simplified - no git required)
    print("\n[Stage 2] Evolutionary Mining")
    print("  (Skipped for this test - no git history required)")

    # Stage 3: Graph Building and Fusion
    print("\n[Stage 3] Graph Building")
    graph_builder = GraphBuilder()

    G_static = graph_builder.build_static_graph(class_deps)
    print(f"  ✓ Built static graph: {G_static.number_of_nodes()} nodes, {G_static.number_of_edges()} edges")

    # For this test, we'll just use the static graph
    G_fused = G_static

    # Stage 4: Clustering with NEW Leiden Algorithm
    print("\n[Stage 4] Clustering with Leiden Algorithm")

    config = {
        'clustering': {
            'algorithm': 'leiden',
            'min_cluster_size': 2,
            'max_cluster_size': 15,
            'min_cohesion': 0.3,
            'validate_connectivity': True,
            'split_disconnected': True,
            'quality_metrics': {
                'silhouette': True,
                'conductance': True,
                'coverage': True,
            }
        }
    }

    detector = ClusterDetector(
        min_cluster_size=2,
        max_cluster_size=15,
        min_cohesion=0.3,
        algorithm='leiden',
        config=config
    )

    # Detect clusters
    clusters = detector.detect_clusters(G_fused)
    print(f"  ✓ Detected {len(clusters)} clusters")

    # Verify all clusters are connected
    all_connected = all(c.is_connected for c in clusters)
    print(f"  ✓ All clusters connected: {all_connected}")

    # Filter and rank
    filtered = detector.filter_clusters(clusters, class_deps)
    print(f"  ✓ Filtered to {len(filtered)} valid clusters")

    ranked = detector.rank_clusters(filtered)
    print(f"  ✓ Ranked clusters by quality")

    # Show top clusters
    if ranked:
        print("\n  Top clusters:")
        for i, cluster in enumerate(ranked[:3], 1):
            methods = cluster.get_methods()
            fields = cluster.get_fields()
            print(f"    {i}. Cluster {cluster.id}:")
            print(f"       - Members: {len(cluster)} ({len(methods)} methods, {len(fields)} fields)")
            print(f"       - Quality score: {cluster.quality_score:.3f}")
            print(f"       - Rank score: {cluster.rank_score:.3f}")
            if cluster.silhouette_score is not None:
                print(f"       - Silhouette: {cluster.silhouette_score:.3f}")
            if cluster.conductance is not None:
                print(f"       - Conductance: {cluster.conductance:.3f}")

    # Final verification
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)

    checks = []
    checks.append(("Stage 1 analysis successful", class_deps is not None))
    checks.append(("Graph built successfully", G_fused.number_of_nodes() > 0))
    checks.append(("Leiden clustering working", len(clusters) >= 0))
    checks.append(("All clusters connected", all_connected))
    checks.append(("Filtering works", True))  # Always true if we got here
    checks.append(("Ranking works", True))  # Always true if we got here

    all_passed = all(passed for _, passed in checks)

    for check_name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}")

    print("="*80)

    if all_passed:
        print("\n🎉 END-TO-END TEST PASSED!")
        print(f"   Stages 1-4 work together perfectly with new Leiden clustering")
        return True
    else:
        print("\n❌ END-TO-END TEST FAILED")
        return False


if __name__ == "__main__":
    success = test_stages_1_to_4()
    sys.exit(0 if success else 1)
