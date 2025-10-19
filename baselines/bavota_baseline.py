"""Bavota et al. baseline using static dependencies and semantic similarity."""

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import networkx as nx
import community as community_louvain
from typing import List, Dict
from dataclasses import dataclass

from genec.core.dependency_analyzer import DependencyAnalyzer, ClassDependencies
from genec.core.graph_builder import GraphBuilder
from genec.core.cluster_detector import Cluster
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class BavotaSuggestion:
    """Bavota baseline refactoring suggestion."""
    cluster_id: int
    member_names: List[str]
    member_types: Dict[str, str]
    quality_score: float


class BavotaBaseline:
    """
    Baseline approach based on Bavota et al.

    Uses static dependencies + semantic similarity (TF-IDF on identifier names).
    No LLM involvement.
    """

    def __init__(
        self,
        min_cluster_size: int = 3,
        max_cluster_size: int = 15,
        semantic_weight: float = 0.3
    ):
        """
        Initialize Bavota baseline.

        Args:
            min_cluster_size: Minimum cluster size
            max_cluster_size: Maximum cluster size
            semantic_weight: Weight for semantic similarity (vs static dependencies)
        """
        self.min_cluster_size = min_cluster_size
        self.max_cluster_size = max_cluster_size
        self.semantic_weight = semantic_weight

        self.dependency_analyzer = DependencyAnalyzer()
        self.graph_builder = GraphBuilder()
        self.logger = get_logger(self.__class__.__name__)

    def run(self, class_file: str) -> List[BavotaSuggestion]:
        """
        Run Bavota baseline on a class file.

        Args:
            class_file: Path to Java class file

        Returns:
            List of baseline suggestions
        """
        self.logger.info(f"Running Bavota baseline on {class_file}")

        # Analyze dependencies
        class_deps = self.dependency_analyzer.analyze_class(class_file)
        if not class_deps:
            self.logger.error("Failed to analyze class")
            return []

        # Build static dependency graph
        G_static = self.graph_builder.build_static_graph(class_deps)

        # Calculate semantic similarity
        semantic_sim = self._calculate_semantic_similarity(class_deps)

        # Combine static and semantic into unified graph
        G_combined = self._combine_graphs(G_static, semantic_sim, class_deps)

        # Apply clustering
        clusters = self._detect_clusters(G_combined)

        # Filter clusters
        filtered_clusters = self._filter_clusters(clusters)

        # Convert to suggestions
        suggestions = []
        for cluster in filtered_clusters:
            suggestion = BavotaSuggestion(
                cluster_id=cluster.id,
                member_names=cluster.member_names,
                member_types=cluster.member_types,
                quality_score=cluster.quality_score
            )
            suggestions.append(suggestion)

        self.logger.info(f"Generated {len(suggestions)} baseline suggestions")

        return suggestions

    def _calculate_semantic_similarity(self, class_deps: ClassDependencies) -> np.ndarray:
        """
        Calculate semantic similarity between members using TF-IDF on identifier names.

        Args:
            class_deps: Class dependencies

        Returns:
            Similarity matrix
        """
        members = class_deps.member_names

        if not members:
            return np.zeros((0, 0))

        # Extract text from identifiers (split camelCase/snake_case)
        texts = []
        for member in members:
            # Split camelCase
            text = self._split_identifier(member)
            texts.append(text)

        # Calculate TF-IDF
        vectorizer = TfidfVectorizer(lowercase=True, token_pattern=r'\b\w+\b')

        try:
            tfidf_matrix = vectorizer.fit_transform(texts)
            # Calculate cosine similarity
            similarity_matrix = cosine_similarity(tfidf_matrix)
        except:
            # Fallback to zero similarity if TF-IDF fails
            similarity_matrix = np.zeros((len(members), len(members)))

        return similarity_matrix

    def _split_identifier(self, identifier: str) -> str:
        """
        Split identifier into words.

        Handles camelCase, snake_case, etc.

        Args:
            identifier: Identifier name

        Returns:
            Space-separated words
        """
        import re

        # Split camelCase
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1 \2', identifier)
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1 \2', s1)

        # Split on underscores and other separators
        s3 = re.sub(r'[_\-\.]', ' ', s2)

        return s3.lower()

    def _combine_graphs(
        self,
        G_static: nx.Graph,
        semantic_sim: np.ndarray,
        class_deps: ClassDependencies
    ) -> nx.Graph:
        """
        Combine static and semantic graphs.

        Args:
            G_static: Static dependency graph
            semantic_sim: Semantic similarity matrix
            class_deps: Class dependencies

        Returns:
            Combined graph
        """
        G_combined = G_static.copy()

        members = class_deps.member_names
        n = len(members)

        # Normalize static weights
        static_weights = [d['weight'] for u, v, d in G_static.edges(data=True)]
        max_static = max(static_weights) if static_weights else 1.0

        # Add/update edges with combined weight
        for i in range(n):
            for j in range(i + 1, n):
                member_i = members[i]
                member_j = members[j]

                # Get static weight (normalized)
                static_weight = 0.0
                if G_static.has_edge(member_i, member_j):
                    static_weight = G_static[member_i][member_j]['weight'] / max_static

                # Get semantic weight
                semantic_weight = semantic_sim[i][j]

                # Combine
                combined_weight = (
                    (1 - self.semantic_weight) * static_weight +
                    self.semantic_weight * semantic_weight
                )

                # Add edge if weight is significant
                if combined_weight > 0.1:
                    G_combined.add_edge(
                        member_i,
                        member_j,
                        weight=combined_weight
                    )

        return G_combined

    def _detect_clusters(self, G: nx.Graph) -> List[Cluster]:
        """
        Detect clusters using Louvain algorithm.

        Args:
            G: Combined graph

        Returns:
            List of clusters
        """
        if G.number_of_nodes() == 0:
            return []

        # Run Louvain
        partition = community_louvain.best_partition(G, weight='weight', random_state=42)

        # Group into clusters
        communities: Dict[int, List[str]] = {}
        for node, comm_id in partition.items():
            if comm_id not in communities:
                communities[comm_id] = []
            communities[comm_id].append(node)

        # Create Cluster objects
        clusters = []
        for cluster_id, members in communities.items():
            member_types = {}
            for member in members:
                node_type = G.nodes[member].get('type', 'method')
                member_types[member] = node_type

            cluster = Cluster(
                id=cluster_id,
                member_names=members,
                member_types=member_types
            )

            # Calculate quality score (simple internal cohesion)
            cluster.quality_score = self._calculate_cluster_quality(cluster, G)

            clusters.append(cluster)

        return clusters

    def _calculate_cluster_quality(self, cluster: Cluster, G: nx.Graph) -> float:
        """Calculate cluster quality score."""
        members = set(cluster.member_names)

        # Calculate internal edge weights
        internal_weights = []
        for u in members:
            for v in members:
                if u < v and G.has_edge(u, v):
                    internal_weights.append(G[u][v]['weight'])

        if internal_weights:
            return np.mean(internal_weights)
        else:
            return 0.0

    def _filter_clusters(self, clusters: List[Cluster]) -> List[Cluster]:
        """Filter clusters by size and quality."""
        filtered = []

        for cluster in clusters:
            # Size constraints
            if len(cluster) < self.min_cluster_size:
                continue
            if len(cluster) > self.max_cluster_size:
                continue

            # Must have at least one method
            if len(cluster.get_methods()) == 0:
                continue

            filtered.append(cluster)

        # Sort by quality
        filtered.sort(key=lambda c: c.quality_score, reverse=True)

        return filtered
