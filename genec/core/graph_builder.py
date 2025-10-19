"""Graph builder for dependency and evolutionary coupling graphs."""

import networkx as nx
import matplotlib.pyplot as plt
from typing import Dict, Set, Optional, Tuple
from pathlib import Path

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
                node_type = 'method'
            else:
                node_type = 'field'

            G.add_node(member, type=node_type)

        # Add edges from dependency matrix
        n = len(class_deps.member_names)
        for i in range(n):
            for j in range(i + 1, n):  # Only upper triangle (undirected graph)
                weight = max(
                    class_deps.dependency_matrix[i][j],
                    class_deps.dependency_matrix[j][i]
                )

                if weight > 0:
                    G.add_edge(
                        class_deps.member_names[i],
                        class_deps.member_names[j],
                        weight=weight,
                        edge_type='static'
                    )

        self.logger.info(
            f"Static graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges"
        )

        return G

    def build_evolutionary_graph(
        self,
        evo_data: EvolutionaryData,
        method_signatures: Optional[Dict[str, str]] = None
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

            G.add_node(node_name, type='method')

        # Add edges from coupling strengths
        for (m1, m2), strength in evo_data.coupling_strengths.items():
            # Map to signatures if provided
            node1 = method_signatures.get(m1, m1) if method_signatures else m1
            node2 = method_signatures.get(m2, m2) if method_signatures else m2

            if node1 in G.nodes and node2 in G.nodes:
                G.add_edge(node1, node2, weight=strength, edge_type='evolutionary')

        self.logger.info(
            f"Evolutionary graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges"
        )

        return G

    def fuse_graphs(
        self,
        G_static: nx.Graph,
        G_evo: nx.Graph,
        alpha: float = 0.5,
        edge_threshold: float = 0.1
    ) -> nx.Graph:
        """
        Fuse static and evolutionary graphs.

        Combined weight = alpha * static_weight + (1 - alpha) * evolutionary_weight

        Args:
            G_static: Static dependency graph
            G_evo: Evolutionary coupling graph
            alpha: Weight for static graph (0.5 = equal weight)
            edge_threshold: Minimum weight to keep an edge

        Returns:
            Fused graph
        """
        self.logger.info(
            f"Fusing graphs with alpha={alpha}, threshold={edge_threshold}"
        )

        G_fused = nx.Graph()

        # Add all nodes from both graphs
        for node, data in G_static.nodes(data=True):
            G_fused.add_node(node, **data)

        for node, data in G_evo.nodes(data=True):
            if node not in G_fused:
                G_fused.add_node(node, **data)

        # Normalize edge weights to [0, 1] range
        static_weights = [d['weight'] for u, v, d in G_static.edges(data=True)]
        evo_weights = [d['weight'] for u, v, d in G_evo.edges(data=True)]

        max_static = max(static_weights) if static_weights else 1.0
        max_evo = max(evo_weights) if evo_weights else 1.0

        # Combine edges
        all_edges = set()

        # Process static edges
        for u, v, data in G_static.edges(data=True):
            all_edges.add((u, v))

        # Process evolutionary edges
        for u, v, data in G_evo.edges(data=True):
            all_edges.add((u, v))

        # Add fused edges
        for u, v in all_edges:
            static_weight = 0.0
            evo_weight = 0.0

            if G_static.has_edge(u, v):
                static_weight = G_static[u][v]['weight'] / max_static

            if G_evo.has_edge(u, v):
                evo_weight = G_evo[u][v]['weight'] / max_evo

            # Fuse weights
            fused_weight = alpha * static_weight + (1 - alpha) * evo_weight

            # Only add edge if above threshold
            if fused_weight >= edge_threshold:
                G_fused.add_edge(
                    u, v,
                    weight=fused_weight,
                    static_weight=static_weight,
                    evo_weight=evo_weight
                )

        self.logger.info(
            f"Fused graph: {G_fused.number_of_nodes()} nodes, "
            f"{G_fused.number_of_edges()} edges"
        )

        return G_fused

    def visualize_graph(
        self,
        G: nx.Graph,
        output_file: Optional[str] = None,
        title: str = "Dependency Graph",
        figsize: Tuple[int, int] = (12, 8)
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
        method_nodes = [n for n, d in G.nodes(data=True) if d.get('type') == 'method']
        field_nodes = [n for n, d in G.nodes(data=True) if d.get('type') == 'field']

        # Draw nodes
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=method_nodes,
            node_color='lightblue',
            node_size=500,
            label='Methods'
        )

        nx.draw_networkx_nodes(
            G, pos,
            nodelist=field_nodes,
            node_color='lightgreen',
            node_size=300,
            label='Fields'
        )

        # Draw edges with varying thickness based on weight
        edges = G.edges()
        weights = [G[u][v]['weight'] for u, v in edges]

        if weights:
            max_weight = max(weights)
            edge_widths = [3 * (w / max_weight) for w in weights]

            nx.draw_networkx_edges(
                G, pos,
                edgelist=edges,
                width=edge_widths,
                alpha=0.6
            )

        # Draw labels (truncate long names)
        labels = {n: n[:20] + '...' if len(n) > 20 else n for n in G.nodes()}
        nx.draw_networkx_labels(G, pos, labels, font_size=8)

        plt.title(title)
        plt.legend()
        plt.axis('off')
        plt.tight_layout()

        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
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

    def get_graph_metrics(self, G: nx.Graph) -> Dict[str, float]:
        """
        Calculate various graph metrics.

        Args:
            G: NetworkX graph

        Returns:
            Dictionary of metric names to values
        """
        metrics = {
            'num_nodes': G.number_of_nodes(),
            'num_edges': G.number_of_edges(),
            'density': nx.density(G) if G.number_of_nodes() > 1 else 0.0,
            'num_components': nx.number_connected_components(G),
        }

        # Average clustering coefficient
        if G.number_of_nodes() > 0:
            metrics['avg_clustering'] = nx.average_clustering(G)

        # Average degree
        if G.number_of_nodes() > 0:
            degrees = [d for n, d in G.degree()]
            metrics['avg_degree'] = sum(degrees) / len(degrees)

        return metrics
