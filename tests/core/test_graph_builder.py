"""Tests for genec.core.graph_builder.GraphBuilder."""

import networkx as nx
import numpy as np
import pytest
from dataclasses import dataclass, field as dataclass_field
from unittest.mock import MagicMock

from genec.core.graph_builder import GraphBuilder
from genec.core.dependency_analyzer import ClassDependencies, MethodInfo, FieldInfo
from genec.core.evolutionary_miner import EvolutionaryData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_method(name: str, sig: str | None = None) -> MethodInfo:
    if sig is None:
        sig = f"{name}()"
    return MethodInfo(
        name=name,
        signature=sig,
        return_type="void",
        modifiers=["public"],
        parameters=[],
        start_line=1,
        end_line=10,
        body="",
    )


def _make_field(name: str, ftype: str = "int") -> FieldInfo:
    return FieldInfo(name=name, type=ftype, modifiers=["private"], line_number=1)


def _make_class_deps(
    methods: list[MethodInfo] | None = None,
    fields: list[FieldInfo] | None = None,
    matrix: np.ndarray | None = None,
) -> ClassDependencies:
    methods = methods or []
    fields = fields or []
    member_names = [m.signature for m in methods] + [f.name for f in fields]
    if matrix is None:
        n = len(member_names)
        matrix = np.zeros((n, n))
    return ClassDependencies(
        class_name="TestClass",
        package_name="com.test",
        file_path="/tmp/TestClass.java",
        methods=methods,
        fields=fields,
        constructors=[],
        dependency_matrix=matrix,
        member_names=member_names,
    )


# ---------------------------------------------------------------------------
# TestBuildStaticGraph
# ---------------------------------------------------------------------------

class TestBuildStaticGraph:
    def test_creates_graph_from_dependency_matrix(self):
        """Two methods with a dependency should produce an edge."""
        m1 = _make_method("methodA")
        m2 = _make_method("methodB")
        matrix = np.array([[0.0, 0.8], [0.8, 0.0]])
        deps = _make_class_deps(methods=[m1, m2], matrix=matrix)

        builder = GraphBuilder()
        G = builder.build_static_graph(deps)

        assert isinstance(G, nx.Graph)
        assert G.number_of_nodes() == 2
        assert G.number_of_edges() == 1
        # The edge weight should be 0.8 (max of symmetric entries)
        u, v = list(G.edges())[0]
        assert G[u][v]["weight"] == pytest.approx(0.8)

    def test_no_edges_for_zero_weights(self):
        """Zero-weight matrix should produce nodes but no edges."""
        m1 = _make_method("a")
        m2 = _make_method("b")
        matrix = np.array([[0.0, 0.0], [0.0, 0.0]])
        deps = _make_class_deps(methods=[m1, m2], matrix=matrix)

        builder = GraphBuilder()
        G = builder.build_static_graph(deps)

        assert G.number_of_nodes() == 2
        assert G.number_of_edges() == 0

    def test_empty_deps_returns_empty_graph(self):
        """No members at all should give an empty graph."""
        deps = _make_class_deps()

        builder = GraphBuilder()
        G = builder.build_static_graph(deps)

        assert G.number_of_nodes() == 0
        assert G.number_of_edges() == 0

    def test_methods_and_fields_become_nodes(self):
        """Both methods and fields should appear as nodes with correct type."""
        m1 = _make_method("doWork")
        f1 = _make_field("count")
        matrix = np.array([[0.0, 0.5], [0.5, 0.0]])
        deps = _make_class_deps(methods=[m1], fields=[f1], matrix=matrix)

        builder = GraphBuilder()
        G = builder.build_static_graph(deps)

        assert G.number_of_nodes() == 2
        assert G.nodes["doWork()"]["type"] == "method"
        assert G.nodes["count"]["type"] == "field"

    def test_asymmetric_matrix_uses_max(self):
        """If matrix[i][j] != matrix[j][i], the edge gets the max."""
        m1 = _make_method("x")
        m2 = _make_method("y")
        matrix = np.array([[0.0, 0.3], [0.7, 0.0]])
        deps = _make_class_deps(methods=[m1, m2], matrix=matrix)

        builder = GraphBuilder()
        G = builder.build_static_graph(deps)

        assert G.number_of_edges() == 1
        u, v = list(G.edges())[0]
        assert G[u][v]["weight"] == pytest.approx(0.7)

    def test_three_methods_triangle(self):
        """Three mutually-dependent methods should produce three edges."""
        methods = [_make_method("a"), _make_method("b"), _make_method("c")]
        matrix = np.array([
            [0.0, 0.5, 0.3],
            [0.5, 0.0, 0.4],
            [0.3, 0.4, 0.0],
        ])
        deps = _make_class_deps(methods=methods, matrix=matrix)

        builder = GraphBuilder()
        G = builder.build_static_graph(deps)

        assert G.number_of_nodes() == 3
        assert G.number_of_edges() == 3


# ---------------------------------------------------------------------------
# TestBuildEvolutionaryGraph
# ---------------------------------------------------------------------------

class TestBuildEvolutionaryGraph:
    def test_basic_evolutionary_graph(self):
        """Coupling strengths should become edges in the graph."""
        evo = EvolutionaryData(
            class_file="Test.java",
            method_names={"doA()", "doB()"},
            coupling_strengths={("doA()", "doB()"): 0.75},
        )

        builder = GraphBuilder()
        G = builder.build_evolutionary_graph(evo)

        assert G.number_of_nodes() == 2
        assert G.has_edge("doA()", "doB()")
        assert G["doA()"]["doB()"]["weight"] == pytest.approx(0.75)

    def test_no_coupling_no_edges(self):
        """Methods with no coupling strengths produce no edges."""
        evo = EvolutionaryData(
            class_file="Test.java",
            method_names={"doA()", "doB()"},
            coupling_strengths={},
        )

        builder = GraphBuilder()
        G = builder.build_evolutionary_graph(evo)

        assert G.number_of_nodes() == 2
        assert G.number_of_edges() == 0

    def test_method_signatures_mapping(self):
        """method_signatures should map short names to full signatures."""
        evo = EvolutionaryData(
            class_file="Test.java",
            method_names={"doA", "doB"},
            coupling_strengths={("doA", "doB"): 0.6},
        )
        sig_map = {"doA": "doA()", "doB": "doB(int)"}

        builder = GraphBuilder()
        G = builder.build_evolutionary_graph(evo, method_signatures=sig_map)

        assert G.has_node("doA()")
        assert G.has_node("doB(int)")
        assert G.has_edge("doA()", "doB(int)")


# ---------------------------------------------------------------------------
# TestFuseGraphs
# ---------------------------------------------------------------------------

class TestFuseGraphs:
    def test_alpha_one_uses_only_static(self):
        """alpha=1.0 should weight only the static graph."""
        builder = GraphBuilder()
        G_s = nx.Graph()
        G_s.add_edge("a", "b", weight=1.0)
        G_e = nx.Graph()
        G_e.add_edge("a", "b", weight=0.5)

        G = builder.fuse_graphs(G_s, G_e, alpha=1.0, edge_threshold=0.0)

        assert G.has_edge("a", "b")
        # fused = 1.0 * (1.0/1.0) + 0.0 * (0.5/0.5) = 1.0
        assert G["a"]["b"]["weight"] == pytest.approx(1.0)

    def test_alpha_zero_uses_only_evolutionary(self):
        """alpha=0.0 should weight only the evolutionary graph."""
        builder = GraphBuilder()
        G_s = nx.Graph()
        G_s.add_edge("a", "b", weight=1.0)
        G_e = nx.Graph()
        G_e.add_edge("c", "d", weight=0.5)

        G = builder.fuse_graphs(G_s, G_e, alpha=0.0, edge_threshold=0.0)

        # c-d: fused = 0.0*0 + 1.0*(0.5/0.5) = 1.0  (only evo edge)
        assert G.has_edge("c", "d")
        # a-b: fused = 0.0*(1.0/1.0) + 1.0*0 = 0.0  (zero evo weight, should still exist if >= threshold)
        assert G.has_edge("a", "b")
        assert G["a"]["b"]["weight"] == pytest.approx(0.0)

    def test_empty_evolutionary_preserves_static(self):
        """Empty evolutionary graph should keep static edges (scaled by alpha)."""
        builder = GraphBuilder()
        G_s = nx.Graph()
        G_s.add_edge("a", "b", weight=0.8)
        G_e = nx.Graph()

        G = builder.fuse_graphs(G_s, G_e, alpha=0.6, edge_threshold=0.0)

        assert G.has_edge("a", "b")
        # normalized static weight = 0.8/0.8 = 1.0, fused = 0.6 * 1.0 = 0.6
        assert G["a"]["b"]["weight"] == pytest.approx(0.6)

    def test_empty_static_preserves_evolutionary(self):
        """Empty static graph should keep evo edges (scaled by 1-alpha)."""
        builder = GraphBuilder()
        G_s = nx.Graph()
        G_e = nx.Graph()
        G_e.add_edge("x", "y", weight=1.0)

        G = builder.fuse_graphs(G_s, G_e, alpha=0.6, edge_threshold=0.0)

        assert G.has_edge("x", "y")
        # fused = (1-0.6) * 1.0 = 0.4
        assert G["x"]["y"]["weight"] == pytest.approx(0.4)

    def test_edge_threshold_filters_weak_edges(self):
        """Edges below the threshold should be dropped."""
        builder = GraphBuilder()
        G_s = nx.Graph()
        G_s.add_edge("a", "b", weight=1.0)
        G_s.add_edge("c", "d", weight=0.1)
        G_e = nx.Graph()

        # alpha=1.0, threshold=0.5 => edge a-b (1.0) passes, c-d (0.1/1.0=0.1) fails
        G = builder.fuse_graphs(G_s, G_e, alpha=1.0, edge_threshold=0.5)

        assert G.has_edge("a", "b")
        assert not G.has_edge("c", "d")

    def test_both_graphs_empty(self):
        """Fusing two empty graphs should return an empty graph."""
        builder = GraphBuilder()
        G = builder.fuse_graphs(nx.Graph(), nx.Graph(), alpha=0.5)
        assert G.number_of_nodes() == 0
        assert G.number_of_edges() == 0

    def test_balanced_fusion(self):
        """alpha=0.5 should give equal weight to both sources."""
        builder = GraphBuilder()
        G_s = nx.Graph()
        G_s.add_edge("a", "b", weight=1.0)
        G_e = nx.Graph()
        G_e.add_edge("a", "b", weight=1.0)

        G = builder.fuse_graphs(G_s, G_e, alpha=0.5, edge_threshold=0.0)

        # Both normalized to 1.0, fused = 0.5*1.0 + 0.5*1.0 = 1.0
        assert G["a"]["b"]["weight"] == pytest.approx(1.0)

    def test_nodes_from_both_graphs_present(self):
        """All nodes from both graphs should appear in the fused graph."""
        builder = GraphBuilder()
        G_s = nx.Graph()
        G_s.add_node("a", type="method")
        G_e = nx.Graph()
        G_e.add_node("b", type="method")

        G = builder.fuse_graphs(G_s, G_e, alpha=0.5)

        assert "a" in G.nodes
        assert "b" in G.nodes


# ---------------------------------------------------------------------------
# TestCentralityMetrics
# ---------------------------------------------------------------------------

class TestCentralityMetrics:
    def test_centrality_on_simple_graph(self):
        """A simple path graph should return all four metric types."""
        builder = GraphBuilder()
        G = nx.Graph()
        G.add_edges_from([("a", "b", {"weight": 1.0}), ("b", "c", {"weight": 1.0})])

        metrics = builder.calculate_centrality_metrics(G, top_n=5)

        assert "degree_centrality" in metrics
        assert "betweenness_centrality" in metrics
        assert "pagerank" in metrics
        # Node "b" should have highest betweenness (it's the bridge)
        assert max(metrics["betweenness_centrality"], key=metrics["betweenness_centrality"].get) == "b"

    def test_centrality_on_empty_graph(self):
        """Empty graph should return empty dict."""
        builder = GraphBuilder()
        G = nx.Graph()

        metrics = builder.calculate_centrality_metrics(G)

        assert metrics == {}

    def test_top_n_limits_results(self):
        """top_n=1 should return at most 1 entry per metric."""
        builder = GraphBuilder()
        G = nx.Graph()
        G.add_edges_from([
            ("a", "b", {"weight": 1.0}),
            ("b", "c", {"weight": 1.0}),
            ("c", "d", {"weight": 1.0}),
        ])

        metrics = builder.calculate_centrality_metrics(G, top_n=1)

        for metric_name, scores in metrics.items():
            assert len(scores) <= 1, f"{metric_name} has more than 1 entry"

    def test_single_node_graph(self):
        """Graph with one node should still compute metrics."""
        builder = GraphBuilder()
        G = nx.Graph()
        G.add_node("lone")

        metrics = builder.calculate_centrality_metrics(G, top_n=5)

        assert "degree_centrality" in metrics
        # networkx returns 1.0 for degree centrality of a single node (N-1=0 edge case)
        assert "lone" in metrics["degree_centrality"]


# ---------------------------------------------------------------------------
# TestGraphMetrics
# ---------------------------------------------------------------------------

class TestGraphMetrics:
    def test_metrics_on_simple_graph(self):
        builder = GraphBuilder()
        G = nx.Graph()
        G.add_edges_from([("a", "b"), ("b", "c")])

        metrics = builder.get_graph_metrics(G)

        assert metrics["num_nodes"] == 3
        assert metrics["num_edges"] == 2
        assert metrics["num_components"] == 1
        assert "density" in metrics
        assert "avg_degree" in metrics
        assert "avg_clustering" in metrics

    def test_metrics_on_empty_graph(self):
        builder = GraphBuilder()
        G = nx.Graph()

        metrics = builder.get_graph_metrics(G)

        assert metrics["num_nodes"] == 0
        assert metrics["num_edges"] == 0
        assert metrics["density"] == 0.0

    def test_disconnected_graph_components(self):
        """Two disconnected edges should report 2 components."""
        builder = GraphBuilder()
        G = nx.Graph()
        G.add_edge("a", "b")
        G.add_edge("c", "d")

        metrics = builder.get_graph_metrics(G)

        assert metrics["num_components"] == 2
        assert metrics["num_nodes"] == 4
        assert metrics["num_edges"] == 2


# ---------------------------------------------------------------------------
# TestConnectedComponents
# ---------------------------------------------------------------------------

class TestConnectedComponents:
    def test_single_component(self):
        builder = GraphBuilder()
        G = nx.Graph()
        G.add_edges_from([("a", "b"), ("b", "c")])

        components = builder.get_connected_components(G)

        assert len(components) == 1
        assert {"a", "b", "c"} == components[0]

    def test_two_components(self):
        builder = GraphBuilder()
        G = nx.Graph()
        G.add_edge("a", "b")
        G.add_edge("c", "d")

        components = builder.get_connected_components(G)

        assert len(components) == 2


# ---------------------------------------------------------------------------
# TestAddCentralityToGraph
# ---------------------------------------------------------------------------

class TestAddCentralityToGraph:
    def test_adds_attributes_to_nodes(self):
        builder = GraphBuilder()
        G = nx.Graph()
        G.add_edge("a", "b", weight=1.0)

        G_enriched = builder.add_centrality_to_graph(G)

        # Should have centrality attributes on each node
        for node in G_enriched.nodes():
            assert "degree_centrality" in G_enriched.nodes[node]
            assert "pagerank" in G_enriched.nodes[node]
