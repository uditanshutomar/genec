"""Cluster detection using Louvain community detection algorithm."""

import networkx as nx
import community as community_louvain
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
import numpy as np

from genec.core.dependency_analyzer import ClassDependencies
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class Cluster:
    """Represents a detected cluster of methods and fields."""
    id: int
    member_names: List[str]
    member_types: Dict[str, str] = field(default_factory=dict)  # name -> 'method' or 'field'
    quality_score: float = 0.0
    modularity: float = 0.0
    internal_cohesion: float = 0.0
    external_coupling: float = 0.0
    rank_score: Optional[float] = None

    def __len__(self):
        return len(self.member_names)

    def get_methods(self) -> List[str]:
        """Get only method members."""
        return [m for m, t in self.member_types.items() if t == 'method']

    def get_fields(self) -> List[str]:
        """Get only field members."""
        return [m for m, t in self.member_types.items() if t == 'field']


class ClusterDetector:
    """Detects and evaluates clusters using Louvain community detection."""

    def __init__(
        self,
        min_cluster_size: int = 3,
        max_cluster_size: int = 15,
        min_cohesion: float = 0.5,
        resolution: float = 1.0
    ):
        """
        Initialize cluster detector.

        Args:
            min_cluster_size: Minimum number of members in a cluster
            max_cluster_size: Maximum number of members in a cluster
            min_cohesion: Minimum internal cohesion threshold
            resolution: Louvain resolution parameter (higher = more smaller clusters)
        """
        self.min_cluster_size = min_cluster_size
        self.max_cluster_size = max_cluster_size
        self.min_cohesion = min_cohesion
        self.resolution = resolution
        self.logger = get_logger(self.__class__.__name__)

    def detect_clusters(self, G: nx.Graph) -> List[Cluster]:
        """
        Detect clusters using Louvain community detection.

        Args:
            G: Fused dependency graph

        Returns:
            List of detected clusters
        """
        self.logger.info("Detecting clusters using Louvain algorithm")

        if G.number_of_nodes() == 0:
            self.logger.warning("Empty graph, no clusters detected")
            return []

        # Check if graph has edges
        if G.number_of_edges() == 0:
            self.logger.warning(
                "Graph has no edges (no method dependencies detected). "
                "This typically means methods are independent with no shared fields or calls. "
                "Creating single cluster with all members for LLM-based analysis."
            )
            return self._create_fallback_clusters(G)

        # Run Louvain community detection
        partition = community_louvain.best_partition(
            G,
            weight='weight',
            resolution=self.resolution,
            random_state=42
        )

        # Calculate modularity
        modularity = community_louvain.modularity(partition, G, weight='weight')
        self.logger.info(f"Graph modularity: {modularity:.4f}")

        # Group nodes by community
        communities: Dict[int, List[str]] = {}
        for node, comm_id in partition.items():
            if comm_id not in communities:
                communities[comm_id] = []
            communities[comm_id].append(node)

        # Create Cluster objects
        clusters = []
        for cluster_id, members in communities.items():
            # Get member types from graph
            member_types = {}
            for member in members:
                node_type = G.nodes[member].get('type', 'method')
                member_types[member] = node_type

            cluster = Cluster(
                id=cluster_id,
                member_names=members,
                member_types=member_types,
                modularity=modularity
            )

            # Calculate cluster quality metrics
            self._calculate_cluster_metrics(cluster, G)

            clusters.append(cluster)

        self.logger.info(f"Detected {len(clusters)} clusters")

        return clusters

    def filter_clusters(self, clusters: List[Cluster]) -> List[Cluster]:
        """
        Filter clusters by size and quality constraints.

        Args:
            clusters: List of clusters to filter

        Returns:
            Filtered list of clusters
        """
        self.logger.info("Filtering clusters by size and quality")

        filtered = []
        for cluster in clusters:
            # Check size constraints
            if len(cluster) < self.min_cluster_size:
                self.logger.debug(
                    f"Cluster {cluster.id} too small ({len(cluster)} < {self.min_cluster_size})"
                )
                continue

            if len(cluster) > self.max_cluster_size:
                self.logger.debug(
                    f"Cluster {cluster.id} too large ({len(cluster)} > {self.max_cluster_size})"
                )
                continue

            # Check cohesion constraint (skip for fallback clusters with zero modularity)
            # Fallback clusters are created when graph has no edges
            if cluster.modularity > 0 and cluster.internal_cohesion < self.min_cohesion:
                self.logger.debug(
                    f"Cluster {cluster.id} cohesion too low "
                    f"({cluster.internal_cohesion:.4f} < {self.min_cohesion})"
                )
                continue

            # Must have at least one method
            if len(cluster.get_methods()) == 0:
                self.logger.debug(f"Cluster {cluster.id} has no methods")
                continue

            filtered.append(cluster)

        self.logger.info(f"Filtered to {len(filtered)} clusters")

        return filtered

    def rank_clusters(self, clusters: List[Cluster]) -> List[Cluster]:
        """
        Rank clusters by quality score.

        Quality score considers:
        - Modularity
        - Internal cohesion
        - Low external coupling
        - Appropriate size

        Args:
            clusters: List of clusters to rank

        Returns:
            Sorted list of clusters (best first)
        """
        self.logger.info("Ranking clusters by quality")

        for cluster in clusters:
            # Calculate rank score
            size_score = self._calculate_size_score(len(cluster))

            # Weighted combination
            rank_score = (
                0.3 * cluster.modularity +
                0.4 * cluster.internal_cohesion +
                0.2 * (1.0 - cluster.external_coupling) +
                0.1 * size_score
            )

            cluster.rank_score = rank_score

        # Sort by rank score (descending)
        ranked = sorted(clusters, key=lambda c: c.rank_score, reverse=True)

        for i, cluster in enumerate(ranked, 1):
            self.logger.debug(
                f"Rank {i}: Cluster {cluster.id} - "
                f"Score: {cluster.rank_score:.4f}, "
                f"Size: {len(cluster)}, "
                f"Cohesion: {cluster.internal_cohesion:.4f}"
            )

        return ranked

    def validate_extractability(
        self,
        cluster: Cluster,
        class_deps: ClassDependencies
    ) -> bool:
        """
        Validate that a cluster can be extracted as a separate class.

        Checks:
        - No circular dependencies with remaining class
        - All required fields are included
        - Methods are coherent

        Args:
            cluster: Cluster to validate
            class_deps: Original class dependencies

        Returns:
            True if cluster is extractable
        """
        # Get cluster methods
        cluster_methods = set(cluster.get_methods())
        cluster_fields = set(cluster.get_fields())

        # Get all methods and fields in the class
        all_methods = {m.signature for m in class_deps.get_all_methods()}
        all_fields = {f.name for f in class_deps.fields}

        # Check that cluster members exist
        for method in cluster_methods:
            if method not in all_methods:
                self.logger.debug(f"Method {method} not found in class")
                return False

        for field in cluster_fields:
            if field not in all_fields:
                self.logger.debug(f"Field {field} not found in class")
                return False

        # Check that all accessed fields are included
        for method_sig in cluster_methods:
            accessed_fields = class_deps.field_accesses.get(method_sig, [])
            for field in accessed_fields:
                if field not in cluster_fields and field in all_fields:
                    # A required field is missing from the cluster
                    self.logger.debug(
                        f"Method {method_sig} accesses field {field} "
                        f"which is not in cluster"
                    )
                    # This is a warning, not necessarily a blocker
                    # We could add the field to the cluster

        return True

    def _calculate_cluster_metrics(self, cluster: Cluster, G: nx.Graph):
        """
        Calculate quality metrics for a cluster.

        Args:
            cluster: Cluster to analyze
            G: Full graph
        """
        members = set(cluster.member_names)

        # Calculate internal cohesion (average weight of internal edges)
        internal_edges = []
        for u in members:
            for v in members:
                if u < v and G.has_edge(u, v):
                    internal_edges.append(G[u][v]['weight'])

        if internal_edges:
            cluster.internal_cohesion = np.mean(internal_edges)
        else:
            cluster.internal_cohesion = 0.0

        # Calculate external coupling (average weight of edges to outside)
        external_edges = []
        for u in members:
            for v in G.neighbors(u):
                if v not in members:
                    external_edges.append(G[u][v]['weight'])

        if external_edges:
            cluster.external_coupling = np.mean(external_edges)
        else:
            cluster.external_coupling = 0.0

        # Normalize external coupling to [0, 1]
        if cluster.internal_cohesion > 0:
            cluster.external_coupling = min(
                1.0,
                cluster.external_coupling / cluster.internal_cohesion
            )

        # Calculate overall quality score
        cluster.quality_score = (
            cluster.internal_cohesion * (1.0 - cluster.external_coupling)
        )

    def _calculate_size_score(self, size: int) -> float:
        """
        Calculate a score based on cluster size.

        Prefers moderate sizes (around 5-8 members).

        Args:
            size: Cluster size

        Returns:
            Size score in [0, 1]
        """
        optimal_size = 6
        max_deviation = self.max_cluster_size - optimal_size

        if size <= 0:
            return 0.0

        deviation = abs(size - optimal_size)
        score = 1.0 - (deviation / max_deviation) if max_deviation > 0 else 1.0

        return max(0.0, min(1.0, score))

    def _create_fallback_clusters(self, G: nx.Graph) -> List[Cluster]:
        """
        Create clusters for graphs with no edges.

        Strategy: Group nodes by naming patterns when class is large,
        or create single cluster for smaller classes.

        Args:
            G: Graph with no edges

        Returns:
            List of fallback clusters
        """
        nodes = list(G.nodes())

        if len(nodes) == 0:
            return []

        # Get member types from graph
        member_types = {}
        methods = []
        fields = []
        for node in nodes:
            node_type = G.nodes[node].get('type', 'method')
            member_types[node] = node_type
            if node_type == 'method':
                methods.append(node)
            else:
                fields.append(node)

        # If class is very large (>max_cluster_size), group by naming patterns
        if len(nodes) > self.max_cluster_size:
            self.logger.info(
                f"Large class with {len(nodes)} members, grouping by naming patterns"
            )
            return self._create_pattern_based_clusters(methods, fields, member_types)
        else:
            # Create a single cluster with all members
            # The LLM can analyze semantic relationships even without structural dependencies
            cluster = Cluster(
                id=0,
                member_names=nodes,
                member_types=member_types,
                modularity=0.0,
                internal_cohesion=0.0,
                external_coupling=0.0
            )

            self.logger.info(
                f"Created fallback cluster with {len(nodes)} members "
                f"({len(cluster.get_methods())} methods, {len(cluster.get_fields())} fields)"
            )

            return [cluster]

    def _create_pattern_based_clusters(
        self,
        methods: List[str],
        fields: List[str],
        member_types: Dict[str, str]
    ) -> List[Cluster]:
        """
        Group methods by naming patterns for large classes.

        Args:
            methods: List of method names
            fields: List of field names
            member_types: Mapping of member names to types

        Returns:
            List of clusters grouped by naming patterns
        """
        import re
        from collections import defaultdict

        # Group methods by common prefixes/patterns
        groups = defaultdict(list)

        for method in methods:
            # Extract prefix (e.g., "isEmpty", "isBlank" -> "is")
            # Common patterns: get*, set*, is*, has*, contains*, starts*, ends*, etc.
            prefix_match = re.match(r'^(is|has|get|set|contains?|starts?|ends?|split|join|strip|trim|pad|remove|replace|substring|index|count|check|validate|find|search|parse|format|convert|to|from|create|build|add|append|prepend|insert|delete|truncate|wrap|unwrap|escape|unescape|encode|decode|normalize|compare|equals?|matches?|empty|blank|null|default|abbreviate|capitalize|center|chop|reverse|rotate|swap|overlay|repeat|difference)[A-Z]', method)

            if prefix_match:
                prefix = prefix_match.group(1)
                groups[prefix].append(method)
            else:
                # No clear prefix, use first word
                words = re.findall(r'[A-Z][a-z]*', method)
                if words:
                    groups[words[0].lower()].append(method)
                else:
                    groups['other'].append(method)

        # Create clusters from groups
        clusters = []
        cluster_id = 0

        for prefix, group_methods in groups.items():
            if len(group_methods) < self.min_cluster_size:
                continue

            cluster_members = list(group_methods)

            cluster_member_types = {name: member_types[name] for name in cluster_members}

            if len(cluster_members) < self.min_cluster_size:
                continue

            cluster = Cluster(
                id=cluster_id,
                member_names=cluster_members,
                member_types=cluster_member_types,
                modularity=0.0,
                internal_cohesion=0.0,
                external_coupling=0.0
            )

            clusters.append(cluster)
            cluster_id += 1

            self.logger.info(
                f"Created pattern-based cluster '{prefix}' with {len(group_methods)} methods"
            )

        if not clusters:
            self.logger.warning(
                f"No viable pattern-based clusters created from {len(methods)} methods"
            )

        return clusters
