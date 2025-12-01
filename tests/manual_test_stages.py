#!/usr/bin/env python3
"""
Test GenEC pipeline stages individually to measure improvements.

This script runs each stage of the GenEC pipeline independently on CollectionUtils
to validate the critical fixes and measure their impact.
"""

import sys
from pathlib import Path

# Add genec to path
sys.path.insert(0, str(Path(__file__).parent))

from genec.core.dependency_analyzer import DependencyAnalyzer
from genec.core.evolutionary_miner import EvolutionaryMiner
from genec.core.graph_builder import GraphBuilder
from genec.core.cluster_detector import ClusterDetector
from genec.config.models import load_config
import logging
import numpy as np

def print_separator(title):
    """Print a section separator."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")

def test_stage1_dependency_analysis(class_file: str):
    """Test Stage 1: Static dependency analysis."""
    print_separator("STAGE 1: Static Dependency Analysis")

    analyzer = DependencyAnalyzer()
    class_deps = analyzer.analyze_class(class_file)

    if not class_deps:
        print("❌ Failed to analyze class")
        return None

    # Calculate metrics
    all_methods = class_deps.get_all_methods()
    total_calls = sum(len(calls) for calls in class_deps.method_calls.values())
    total_accesses = sum(len(accesses) for accesses in class_deps.field_accesses.values())
    edge_count = np.count_nonzero(class_deps.dependency_matrix)
    methods_with_calls = sum(1 for calls in class_deps.method_calls.values() if calls)

    print(f"Class: {class_deps.class_name}")
    print(f"Methods: {len(class_deps.methods)}")
    print(f"Constructors: {len(class_deps.constructors)}")
    print(f"Fields: {len(class_deps.fields)}")
    print(f"\n📊 Dependency Detection:")
    print(f"  Total method calls detected: {total_calls}")
    print(f"  Total field accesses detected: {total_accesses}")
    print(f"  Total edges in dependency matrix: {edge_count}")
    print(f"  Methods calling other methods: {methods_with_calls}/{len(all_methods)} ({100*methods_with_calls/len(all_methods):.1f}%)")
    print(f"  Avg edges per method: {edge_count/len(all_methods):.2f}")

    # Sample some method calls to verify static detection
    print(f"\n🔍 Sample Method Calls (first 5 methods with calls):")
    count = 0
    for method in all_methods[:10]:
        calls = class_deps.method_calls.get(method.signature, [])
        if calls and count < 5:
            print(f"  {method.name}() calls: {', '.join(calls[:5])}")
            count += 1

    return class_deps

def test_stage2_evolutionary_mining(class_file: str, repo_path: str, config):
    """Test Stage 2: Evolutionary coupling mining."""
    print_separator("STAGE 2: Evolutionary Coupling Mining")

    # Convert to relative path
    class_file_path = Path(class_file).resolve()
    repo_path_obj = Path(repo_path).resolve()

    try:
        relative_path = class_file_path.relative_to(repo_path_obj)
        relative_path_str = str(relative_path)
    except ValueError:
        print(f"❌ Class file not in repo: {class_file}")
        return None

    miner = EvolutionaryMiner(cache_dir=config.cache.directory)
    evo_data = miner.mine_method_cochanges(
        relative_path_str,
        repo_path,
        window_months=config.evolution.window_months,
        min_commits=config.evolution.min_commits
    )

    print(f"File: {relative_path_str}")
    print(f"Time window: {config.evolution.window_months} months")
    print(f"Min commits: {config.evolution.min_commits}")
    print(f"\n📊 Git History Analysis:")
    print(f"  Total commits affecting file: {evo_data.total_commits}")
    print(f"  Methods found in history: {len(evo_data.method_names)}")
    print(f"  Co-change pairs: {len(evo_data.cochange_matrix)}")
    print(f"  Coupling edges: {len(evo_data.coupling_strengths)}")

    if evo_data.coupling_strengths:
        coupling_values = list(evo_data.coupling_strengths.values())
        print(f"\n📈 Coupling Strength Distribution:")
        print(f"  Average: {np.mean(coupling_values):.3f}")
        print(f"  Maximum: {np.max(coupling_values):.3f}")
        print(f"  Minimum: {np.min(coupling_values):.3f}")
        print(f"  Median: {np.median(coupling_values):.3f}")

        # Show strongest couplings
        sorted_couplings = sorted(evo_data.coupling_strengths.items(),
                                  key=lambda x: x[1], reverse=True)
        print(f"\n🔗 Strongest Couplings (top 5):")
        for (m1, m2), strength in sorted_couplings[:5]:
            print(f"  {m1} ↔ {m2}: {strength:.3f}")

    return evo_data

def test_stage3_graph_fusion(class_deps, evo_data, config):
    """Test Stage 3: Graph building and fusion."""
    print_separator("STAGE 3: Graph Building and Fusion")

    builder = GraphBuilder()

    # Build static graph
    print("Building static dependency graph...")
    G_static = builder.build_static_graph(class_deps)
    print(f"✅ Static graph: {G_static.number_of_nodes()} nodes, {G_static.number_of_edges()} edges")

    # Build evolutionary graph
    print("\nBuilding evolutionary coupling graph...")
    method_map = {m.name: m.signature for m in class_deps.get_all_methods()}
    G_evo = builder.build_evolutionary_graph(evo_data, method_map)
    print(f"✅ Evolutionary graph: {G_evo.number_of_nodes()} nodes, {G_evo.number_of_edges()} edges")

    # Fuse graphs
    print(f"\nFusing graphs with alpha={config.fusion.alpha}, threshold={config.fusion.edge_threshold}...")
    G_fused = builder.fuse_graphs(
        G_static,
        G_evo,
        alpha=config.fusion.alpha,
        edge_threshold=config.fusion.edge_threshold
    )

    print(f"✅ Fused graph: {G_fused.number_of_nodes()} nodes, {G_fused.number_of_edges()} edges")

    # Calculate metrics
    metrics = builder.get_graph_metrics(G_fused)
    print(f"\n📊 Graph Metrics:")
    print(f"  Nodes: {metrics['num_nodes']}")
    print(f"  Edges: {metrics['num_edges']}")
    print(f"  Density: {metrics['density']:.4f} ({metrics['density']*100:.2f}%)")
    print(f"  Connected components: {metrics['num_components']}")
    print(f"  Avg clustering coefficient: {metrics.get('avg_clustering', 0):.4f}")
    print(f"  Avg degree: {metrics.get('avg_degree', 0):.2f}")

    # Show contribution breakdown
    static_edges = G_static.number_of_edges()
    evo_edges = G_evo.number_of_edges()
    fused_edges = G_fused.number_of_edges()

    print(f"\n📈 Edge Contribution:")
    print(f"  Static edges: {static_edges}")
    print(f"  Evolutionary edges: {evo_edges}")
    print(f"  Fused edges: {fused_edges}")
    print(f"  Alpha (static weight): {config.fusion.alpha}")
    print(f"  1-Alpha (evolutionary weight): {1-config.fusion.alpha}")

    return G_fused

def test_stage4_clustering(G_fused, class_deps, config):
    """Test Stage 4: Cluster detection and filtering."""
    print_separator("STAGE 4: Cluster Detection and Filtering")

    detector = ClusterDetector(
        min_cluster_size=config.clustering.min_cluster_size,
        max_cluster_size=config.clustering.max_cluster_size,
        min_cohesion=config.clustering.min_cohesion,
        resolution=config.clustering.resolution
    )

    # Detect clusters
    print(f"Running Louvain clustering (resolution={config.clustering.resolution})...")
    all_clusters = detector.detect_clusters(G_fused)
    print(f"✅ Detected {len(all_clusters)} clusters")

    # Show cluster size distribution
    sizes = [len(c) for c in all_clusters]
    print(f"\n📊 Cluster Size Distribution:")
    print(f"  Total clusters: {len(all_clusters)}")
    print(f"  Min size: {min(sizes) if sizes else 0}")
    print(f"  Max size: {max(sizes) if sizes else 0}")
    print(f"  Avg size: {np.mean(sizes) if sizes else 0:.1f}")
    print(f"  Median size: {np.median(sizes) if sizes else 0:.0f}")

    # Filter clusters
    print(f"\nFiltering clusters (min_size={config.clustering.min_cluster_size}, "
          f"max_size={config.clustering.max_cluster_size}, min_cohesion={config.clustering.min_cohesion})...")
    filtered_clusters = detector.filter_clusters(all_clusters, class_deps)
    print(f"✅ {len(filtered_clusters)} clusters passed filters")
    print(f"❌ {len(all_clusters) - len(filtered_clusters)} clusters rejected")

    # Rank clusters
    print(f"\nRanking clusters by quality...")
    ranked_clusters = detector.rank_clusters(filtered_clusters)

    # Show top clusters
    print(f"\n🏆 Top 5 Clusters (by quality score):")
    for i, cluster in enumerate(ranked_clusters[:5], 1):
        methods = cluster.get_methods()
        fields = cluster.get_fields()
        print(f"\n  Cluster {i} (ID: {cluster.id}):")
        print(f"    Size: {len(cluster)} members ({len(methods)} methods, {len(fields)} fields)")
        print(f"    Quality score: {cluster.rank_score:.4f}")
        print(f"    Modularity: {cluster.modularity:.4f}")
        print(f"    Internal cohesion: {cluster.internal_cohesion:.4f}")
        print(f"    External coupling: {cluster.external_coupling:.4f}")
        print(f"    Methods: {', '.join([m.split('(')[0] for m in methods[:5]])}{'...' if len(methods) > 5 else ''}")

    return ranked_clusters

def main():
    """Run stage-by-stage testing."""
    # Configuration
    class_file = "/Users/uditanshutomar/commons-collections/src/main/java/org/apache/commons/collections4/CollectionUtils.java"
    repo_path = "/Users/uditanshutomar/commons-collections"

    print("🚀 GenEC Pipeline Stage-by-Stage Testing")
    print(f"Target: {Path(class_file).name}")
    print(f"Repository: {Path(repo_path).name}")

    # Setup logging
    logging.basicConfig(level=getattr(logging, "INFO"), format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Load config
    print("\n📝 Loading configuration...")
    config = load_config()
    print(f"✅ Config loaded (alpha={config.fusion.alpha})")

    # Test each stage
    class_deps = test_stage1_dependency_analysis(class_file)
    if not class_deps:
        print("\n❌ Stage 1 failed, cannot continue")
        return 1

    evo_data = test_stage2_evolutionary_mining(class_file, repo_path, config)
    if not evo_data:
        print("\n❌ Stage 2 failed, cannot continue")
        return 1

    G_fused = test_stage3_graph_fusion(class_deps, evo_data, config)
    if not G_fused:
        print("\n❌ Stage 3 failed, cannot continue")
        return 1

    ranked_clusters = test_stage4_clustering(G_fused, class_deps, config)

    # Summary
    print_separator("SUMMARY")

    all_methods = class_deps.get_all_methods()
    edge_count = np.count_nonzero(class_deps.dependency_matrix)

    print("📊 Key Metrics:")
    print(f"  Methods analyzed: {len(all_methods)}")
    print(f"  Static edges: {edge_count}")
    print(f"  Evolutionary edges: {len(evo_data.coupling_strengths)}")
    print(f"  Fused graph edges: {G_fused.number_of_edges()}")
    print(f"  Connected components: {G_fused.number_of_connected_components() if hasattr(G_fused, 'number_of_connected_components') else 'N/A'}")
    print(f"  Clusters detected: {len(ranked_clusters)}")

    print("\n✅ Stage-by-stage testing complete!")
    print("\nNext: Run full pipeline with --max-suggestions 5 to test LLM and verification stages")

    return 0

if __name__ == "__main__":
    sys.exit(main())
