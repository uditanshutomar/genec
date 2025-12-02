"""Graph builder for dependency and evolutionary coupling graphs."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

from genec.core.dependency_analyzer import ClassDependencies
from genec.core.evolutionary_miner import EvolutionaryData
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


class GraphBuilder:
    """Builds and fuses static dependency and evolutionary coupling graphs."""

    def __init__(self):
        """Initialize the graph builder."""
        self.logger = get_logger(self.__class__.__name__)

    def build_static_graph(self, class_deps: ClassDependencies) -> nx.Graph:
        """
        Build static dependency graph from class dependencies.

        Nodes: methods and fields
        Edges: weighted by dependency strength (method calls, field accesses, shared fields)

        Args:
            class_deps: ClassDependencies object

        Returns:
            NetworkX graph with weighted edges
        """
        self.logger.info(f"Building static dependency graph for {class_deps.class_name}")

        G = nx.Graph()

        # Add nodes for all members
        for i, member in enumerate(class_deps.member_names):
            # Determine node type
            if i < len(class_deps.get_all_methods()):
                node_type = "method"
            else:
                node_type = "field"

            G.add_node(member, type=node_type)

        # Add edges from dependency matrix
        n = len(class_deps.member_names)
        for i in range(n):
            for j in range(i + 1, n):  # Only upper triangle (undirected graph)
                weight = max(class_deps.dependency_matrix[i][j], class_deps.dependency_matrix[j][i])

                if weight > 0:
                    G.add_edge(
                        class_deps.member_names[i],
                        class_deps.member_names[j],
                        weight=weight,
                        edge_type="static",
                    )

        self.logger.info(f"Static graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

        return G

    def build_evolutionary_graph(
        self, evo_data: EvolutionaryData, method_signatures: dict[str, str] | None = None
    ) -> nx.Graph:
        """
        Build evolutionary coupling graph from co-change data.

        Nodes: methods only (fields don't have evolutionary coupling)
        Edges: weighted by co-change frequency

        Args:
            evo_data: EvolutionaryData object
            method_signatures: Optional mapping from method names to signatures

        Returns:
            NetworkX graph with weighted edges
        """
        self.logger.info("Building evolutionary coupling graph")

        G = nx.Graph()

        # Add nodes for methods
        for method in evo_data.method_names:
            # Try to match to full signature if provided
            node_name = method
            if method_signatures and method in method_signatures:
                node_name = method_signatures[method]

            G.add_node(node_name, type="method")

        # Add edges from coupling strengths
        for (m1, m2), strength in evo_data.coupling_strengths.items():
            # Map to signatures if provided
            node1 = method_signatures.get(m1, m1) if method_signatures else m1
            node2 = method_signatures.get(m2, m2) if method_signatures else m2

            if node1 in G.nodes and node2 in G.nodes:
                G.add_edge(node1, node2, weight=strength, edge_type="evolutionary")

        self.logger.info(
            f"Evolutionary graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges"
        )

        return G

    def fuse_graphs(
        self,
        G_static: nx.Graph,
        G_evo: nx.Graph,
        alpha: float = 0.5,
        edge_threshold: float = 0.1,
        hotspot_data: list[dict] | None = None,
        adaptive_fusion: bool = False,
    ) -> nx.Graph:
        """
        Fuse static and evolutionary graphs.

        Combined weight = alpha * static_weight + (1 - alpha) * evolutionary_weight

        With adaptive fusion enabled, alpha is adjusted per-edge based on hotspot data:
        - Hotspot methods (high change frequency + coupling) get higher evolutionary weight
        - Stable methods get higher static weight

        Args:
            G_static: Static dependency graph
            G_evo: Evolutionary coupling graph
            alpha: Weight for static graph (0.5 = equal weight)
            edge_threshold: Minimum weight to keep an edge
            hotspot_data: Optional list of hotspot dictionaries from Stage 2
            adaptive_fusion: Enable adaptive fusion based on hotspots

        Returns:
            Fused graph with node centrality metrics
        """
        self.logger.info(
            f"Fusing graphs with alpha={alpha}, threshold={edge_threshold}, "
            f"adaptive={adaptive_fusion}"
        )

        G_fused = nx.Graph()

        # Add all nodes from both graphs
        for node, data in G_static.nodes(data=True):
            G_fused.add_node(node, **data)

        for node, data in G_evo.nodes(data=True):
            if node not in G_fused:
                G_fused.add_node(node, **data)

        # Build hotspot lookup for adaptive fusion
        hotspot_scores = {}
        if adaptive_fusion:
            if hotspot_data:
                for hotspot in hotspot_data:
                    method = hotspot.get("method", "")
                    score = hotspot.get("hotspot_score", 0.0)
                    hotspot_scores[method] = score
                self.logger.info(f"Loaded {len(hotspot_scores)} hotspot scores for adaptive fusion")
            else:
                self.logger.warning(
                    f"Adaptive fusion enabled but no hotspot data provided. "
                    f"Falling back to regular fusion with alpha={alpha}"
                )

        # Normalize edge weights to [0, 1] range
        static_weights = [d["weight"] for u, v, d in G_static.edges(data=True)]
        evo_weights = [d["weight"] for u, v, d in G_evo.edges(data=True)]

        max_static = max(static_weights) if static_weights else 1.0
        max_evo = max(evo_weights) if evo_weights else 1.0

        # Combine edges
        all_edges = set()

        # Process static edges
        for u, v, _data in G_static.edges(data=True):
            all_edges.add((u, v))

        # Process evolutionary edges
        for u, v, _data in G_evo.edges(data=True):
            all_edges.add((u, v))

        # Add fused edges
        for u, v in all_edges:
            static_weight = 0.0
            evo_weight = 0.0

            if G_static.has_edge(u, v):
                static_weight = G_static[u][v]["weight"] / max_static

            if G_evo.has_edge(u, v):
                evo_weight = G_evo[u][v]["weight"] / max_evo

            # Adaptive fusion: adjust alpha based on hotspot scores
            edge_alpha = alpha
            if adaptive_fusion and hotspot_scores:
                u_score = hotspot_scores.get(u, 0.0)
                v_score = hotspot_scores.get(v, 0.0)
                avg_hotspot = (u_score + v_score) / 2.0

                # Higher hotspot score → lower alpha (more evolutionary weight)
                # Hotspot score range: [0, 1], alpha range: [0.2, 0.8]
                # High hotspot (1.0) → alpha = 0.2 (80% evolutionary)
                # Low hotspot (0.0) → alpha = 0.8 (80% static)
                edge_alpha = 0.8 - (0.6 * avg_hotspot)

            # Fuse weights
            fused_weight = edge_alpha * static_weight + (1 - edge_alpha) * evo_weight

            # Only add edge if above threshold
            if fused_weight >= edge_threshold:
                G_fused.add_edge(
                    u,
                    v,
                    weight=fused_weight,
                    static_weight=static_weight,
                    evo_weight=evo_weight,
                    alpha=edge_alpha if adaptive_fusion else alpha,
                )

        self.logger.info(
            f"Fused graph: {G_fused.number_of_nodes()} nodes, " f"{G_fused.number_of_edges()} edges"
        )

        return G_fused

    def calculate_centrality_metrics(
        self, G: nx.Graph, top_n: int = 10
    ) -> dict[str, dict[str, float]]:
        """
        Calculate graph centrality metrics for all nodes.

        Computes:
        - Degree centrality: Number of connections (structural importance)
        - Betweenness centrality: How often node lies on shortest paths (bridge role)
        - Eigenvector centrality: Influence based on connections to high-degree nodes
        - PageRank: Google's algorithm for node importance

        Args:
            G: NetworkX graph
            top_n: Number of top nodes to return for each metric

        Returns:
            Dictionary mapping metric names to {node: score} dictionaries
        """
        self.logger.info("Calculating centrality metrics")

        if G.number_of_nodes() == 0:
            self.logger.warning("Empty graph, cannot calculate centrality")
            return {}

        metrics = {}

        # Degree centrality (normalized by N-1)
        try:
            degree_cent = nx.degree_centrality(G)
            metrics["degree_centrality"] = dict(
                sorted(degree_cent.items(), key=lambda x: x[1], reverse=True)[:top_n]
            )
        except Exception as e:
            self.logger.warning(f"Failed to calculate degree centrality: {e}")
            metrics["degree_centrality"] = {}

        # Betweenness centrality (bridge detection)
        try:
            betweenness_cent = nx.betweenness_centrality(G, weight="weight")
            metrics["betweenness_centrality"] = dict(
                sorted(betweenness_cent.items(), key=lambda x: x[1], reverse=True)[:top_n]
            )
        except Exception as e:
            self.logger.warning(f"Failed to calculate betweenness centrality: {e}")
            metrics["betweenness_centrality"] = {}

        # Eigenvector centrality (influence detection)
        try:
            eigenvector_cent = nx.eigenvector_centrality(G, weight="weight", max_iter=1000)
            metrics["eigenvector_centrality"] = dict(
                sorted(eigenvector_cent.items(), key=lambda x: x[1], reverse=True)[:top_n]
            )
        except Exception as e:
            self.logger.warning(f"Failed to calculate eigenvector centrality: {e}")
            metrics["eigenvector_centrality"] = {}

        # PageRank (Google's algorithm)
        try:
            pagerank = nx.pagerank(G, weight="weight")
            metrics["pagerank"] = dict(
                sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:top_n]
            )
        except Exception as e:
            self.logger.warning(f"Failed to calculate PageRank: {e}")
            metrics["pagerank"] = {}

        self.logger.info(f"Calculated {len(metrics)} centrality metrics")
        return metrics

    def add_centrality_to_graph(
        self, G: nx.Graph, centrality_metrics: dict[str, dict[str, float]] | None = None
    ) -> nx.Graph:
        """
        Add centrality metrics as node attributes in the graph.

        Args:
            G: NetworkX graph
            centrality_metrics: Pre-calculated centrality metrics (if None, calculates them)

        Returns:
            Graph with centrality attributes added to nodes
        """
        if centrality_metrics is None:
            centrality_metrics = self.calculate_centrality_metrics(G, top_n=G.number_of_nodes())

        # Add each metric as a node attribute
        for metric_name, node_scores in centrality_metrics.items():
            for node in G.nodes():
                G.nodes[node][metric_name] = node_scores.get(node, 0.0)

        self.logger.info("Added centrality metrics to graph nodes")
        return G

    def visualize_graph(
        self,
        G: nx.Graph,
        output_file: str | None = None,
        title: str = "Dependency Graph",
        figsize: tuple[int, int] = (12, 8),
    ):
        """
        Visualize a graph using matplotlib.

        Args:
            G: NetworkX graph
            output_file: Optional file path to save the figure
            title: Graph title
            figsize: Figure size
        """
        self.logger.info(f"Visualizing graph: {title}")

        plt.figure(figsize=figsize)

        # Use spring layout for positioning
        pos = nx.spring_layout(G, k=0.5, iterations=50, seed=42)

        # Separate nodes by type
        method_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "method"]
        field_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "field"]

        # Draw nodes
        nx.draw_networkx_nodes(
            G, pos, nodelist=method_nodes, node_color="lightblue", node_size=500, label="Methods"
        )

        nx.draw_networkx_nodes(
            G, pos, nodelist=field_nodes, node_color="lightgreen", node_size=300, label="Fields"
        )

        # Draw edges with varying thickness based on weight
        edges = G.edges()
        weights = [G[u][v]["weight"] for u, v in edges]

        if weights:
            max_weight = max(weights)
            edge_widths = [3 * (w / max_weight) for w in weights]

            nx.draw_networkx_edges(G, pos, edgelist=edges, width=edge_widths, alpha=0.6)

        # Draw labels (truncate long names)
        labels = {n: n[:20] + "..." if len(n) > 20 else n for n in G.nodes()}
        nx.draw_networkx_labels(G, pos, labels, font_size=8)

        plt.title(title)
        plt.legend()
        plt.axis("off")
        plt.tight_layout()

        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches="tight")
            self.logger.info(f"Graph saved to {output_file}")
        else:
            plt.show()

        plt.close()

    def get_connected_components(self, G: nx.Graph) -> list:
        """
        Get connected components of the graph.

        Args:
            G: NetworkX graph

        Returns:
            List of sets, each containing nodes in a component
        """
        components = list(nx.connected_components(G))
        self.logger.info(f"Found {len(components)} connected components")
        return components

    def get_graph_metrics(self, G: nx.Graph) -> dict[str, float]:
        """
        Calculate various graph metrics.

        Args:
            G: NetworkX graph

        Returns:
            Dictionary of metric names to values
        """
        metrics = {
            "num_nodes": G.number_of_nodes(),
            "num_edges": G.number_of_edges(),
            "density": nx.density(G) if G.number_of_nodes() > 1 else 0.0,
            "num_components": nx.number_connected_components(G),
        }

        # Average clustering coefficient
        if G.number_of_nodes() > 0:
            metrics["avg_clustering"] = nx.average_clustering(G)

        # Average degree
        if G.number_of_nodes() > 0:
            degrees = [d for n, d in G.degree()]
            metrics["avg_degree"] = sum(degrees) / len(degrees)

        return metrics

    def export_graph(self, G: nx.Graph, output_path: str, format: str = "graphml") -> None:
        """
        Export graph to various formats.

        Supported formats:
        - graphml: GraphML format (XML-based, preserves all attributes)
        - gml: GML format (simple text format)
        - dot: Graphviz DOT format (for visualization)
        - json: JSON node-link format
        - csv: CSV edge list with weights
        - adjlist: Adjacency list format

        Args:
            G: NetworkX graph
            output_path: Output file path (extension will be added if missing)
            format: Export format (graphml, gml, dot, json, csv, adjlist)
        """
        output_path = Path(output_path)

        # Add extension if missing
        if not output_path.suffix:
            output_path = output_path.with_suffix(f".{format}")

        self.logger.info(f"Exporting graph to {format} format: {output_path}")

        try:
            if format == "graphml":
                nx.write_graphml(G, str(output_path))

            elif format == "gml":
                nx.write_gml(G, str(output_path))

            elif format == "dot":
                nx.drawing.nx_pydot.write_dot(G, str(output_path))

            elif format == "json":
                from networkx.readwrite import json_graph

                data = json_graph.node_link_data(G)
                with open(output_path, "w") as f:
                    json.dump(data, f, indent=2)

            elif format == "csv":
                # Export edge list with weights
                with open(output_path, "w") as f:
                    f.write("source,target,weight,static_weight,evo_weight\n")
                    for u, v, data in G.edges(data=True):
                        weight = data.get("weight", 0.0)
                        static_w = data.get("static_weight", 0.0)
                        evo_w = data.get("evo_weight", 0.0)
                        f.write(f"{u},{v},{weight},{static_w},{evo_w}\n")

            elif format == "adjlist":
                nx.write_adjlist(G, str(output_path))

            else:
                raise ValueError(f"Unsupported format: {format}")

            self.logger.info(f"Graph exported successfully to {output_path}")

        except Exception as e:
            self.logger.error(f"Failed to export graph: {e}")
            raise

    def export_centrality_metrics(
        self,
        centrality_metrics: dict[str, dict[str, float]],
        output_path: str,
        format: str = "json",
    ) -> None:
        """
        Export centrality metrics to file.

        Args:
            centrality_metrics: Dictionary of centrality metrics
            output_path: Output file path
            format: Export format (json or csv)
        """
        output_path = Path(output_path)

        if not output_path.suffix:
            output_path = output_path.with_suffix(f".{format}")

        self.logger.info(f"Exporting centrality metrics to {output_path}")

        try:
            if format == "json":
                with open(output_path, "w") as f:
                    json.dump(centrality_metrics, f, indent=2)

            elif format == "csv":
                # Create CSV with all metrics
                with open(output_path, "w") as f:
                    # Get all nodes
                    all_nodes = set()
                    for metric_data in centrality_metrics.values():
                        all_nodes.update(metric_data.keys())

                    # Write header
                    metric_names = list(centrality_metrics.keys())
                    f.write(f"node,{','.join(metric_names)}\n")

                    # Write data
                    for node in sorted(all_nodes):
                        values = [str(centrality_metrics[m].get(node, 0.0)) for m in metric_names]
                        f.write(f"{node},{','.join(values)}\n")

            else:
                raise ValueError(f"Unsupported format: {format}")

            self.logger.info("Centrality metrics exported successfully")

        except Exception as e:
            self.logger.error(f"Failed to export centrality metrics: {e}")
            raise
