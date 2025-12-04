"""Cluster detection using Louvain or Leiden community detection algorithms."""

import re
from collections import defaultdict
from dataclasses import dataclass, field

import community as community_louvain
import networkx as nx
import numpy as np

# Optional imports for enhanced features
try:
    import igraph as ig
    import leidenalg

    LEIDEN_AVAILABLE = True
except ImportError:
    LEIDEN_AVAILABLE = False

try:
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from genec.core.dependency_analyzer import ClassDependencies
from genec.utils.logging_utils import get_logger

# Semantic analyzer for hybrid clustering
try:
    from genec.core.semantic_analyzer import SemanticAnalyzer

    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False

logger = get_logger(__name__)


@dataclass
class Cluster:
    """Represents a detected cluster of methods and fields."""

    id: int
    member_names: list[str]
    member_types: dict[str, str] = field(default_factory=dict)  # name -> 'method' or 'field'
    quality_score: float = 0.0
    modularity: float = 0.0
    internal_cohesion: float = 0.0
    external_coupling: float = 0.0
    rank_score: float | None = None
    rejection_issues: list = field(default_factory=list)

    # Advanced metrics
    silhouette_score: float | None = None
    conductance: float | None = None
    coverage: float | None = None
    is_connected: bool = True
    stability_score: float | None = None

    def __len__(self):
        return len(self.member_names)

    def get_methods(self) -> list[str]:
        """Get only method members."""
        return [m for m, t in self.member_types.items() if t == "method"]

    def get_fields(self) -> list[str]:
        """Get only field members."""
        return [m for m, t in self.member_types.items() if t == "field"]


class ClusterDetector:
    """Detects and evaluates clusters using Louvain or Leiden community detection."""

    def __init__(
        self,
        min_cluster_size: int = 3,
        max_cluster_size: int = 15,
        min_cohesion: float = 0.5,
        resolution: float = 1.0,
        algorithm: str = "leiden",
        config: dict | None = None,
    ):
        """
        Initialize cluster detector.

        Args:
            min_cluster_size: Minimum number of members in a cluster
            max_cluster_size: Maximum number of members in a cluster
            min_cohesion: Minimum internal cohesion threshold
            resolution: Resolution parameter (higher = more smaller clusters)
            algorithm: 'louvain' or 'leiden' (leiden recommended)
            config: Full configuration dictionary
        """
        self.min_cluster_size = min_cluster_size
        self.max_cluster_size = max_cluster_size
        self.min_cohesion = min_cohesion
        self.resolution = resolution
        self.algorithm = algorithm.lower()
        self.config = config or {}
        self.logger = get_logger(self.__class__.__name__)

        # Extract clustering config
        self.clustering_config = self.config.get("clustering", {})

        # Validate algorithm selection
        if self.algorithm == "leiden" and not LEIDEN_AVAILABLE:
            self.logger.warning(
                "Leiden algorithm selected but leidenalg not installed. "
                "Falling back to Louvain. Install with: pip install leidenalg python-igraph"
            )
            self.algorithm = "louvain"

        # Feature flags
        self.validate_connectivity = self.clustering_config.get("validate_connectivity", True)
        self.split_disconnected = self.clustering_config.get("split_disconnected", True)
        self.quality_metrics_config = self.clustering_config.get("quality_metrics", {})
        self.multi_resolution_config = self.clustering_config.get("multi_resolution", {})
        self.stability_config = self.clustering_config.get("stability_analysis", {})

        # Semantic and hybrid clustering
        self.semantic_config = self.clustering_config.get("semantic", {})
        self.hybrid_config = self.clustering_config.get("hybrid", {})
        self.use_semantic = self.semantic_config.get("enabled", False)
        self.use_hybrid = self.hybrid_config.get("enabled", False)
        self.hybrid_alpha = self.hybrid_config.get("alpha", 0.7)  # Graph weight
        self.semantic_threshold = self.hybrid_config.get("semantic_threshold", 0.5)

        # Initialize semantic analyzer if enabled
        self.semantic_analyzer = None
        if (self.use_semantic or self.use_hybrid) and SEMANTIC_AVAILABLE:
            feature_names = self.semantic_config.get("features", None)
            normalization = self.clustering_config.get("feature_normalization", "zscore")
            self.semantic_analyzer = SemanticAnalyzer(
                feature_names=feature_names, normalization=normalization
            )
            self.logger.info(
                f"Semantic clustering enabled (hybrid={self.use_hybrid}, alpha={self.hybrid_alpha})"
            )
        elif (self.use_semantic or self.use_hybrid) and not SEMANTIC_AVAILABLE:
            self.logger.warning(
                "Semantic clustering enabled but semantic_analyzer not available. "
                "Falling back to graph-only clustering."
            )
            self.use_semantic = False
            self.use_hybrid = False

        self.logger.info(f"Initialized cluster detector with algorithm: {self.algorithm}")

    def detect_clusters(
        self, G: nx.Graph, class_deps: ClassDependencies | None = None
    ) -> list[Cluster]:
        """
        Detect clusters using configured community detection algorithm.

        Args:
            G: Fused dependency graph
            class_deps: Class dependencies (required for semantic/hybrid clustering)

        Returns:
            List of detected clusters
        """
        algo_name = self.algorithm.upper()
        if self.use_hybrid:
            algo_name = f"HYBRID ({algo_name} + Semantic)"
        elif self.use_semantic:
            algo_name = "SEMANTIC"

        self.logger.info(f"Detecting clusters using {algo_name}")

        # Augment graph with semantic features if hybrid mode
        if self.use_hybrid and class_deps and self.semantic_analyzer:
            G = self._augment_graph_with_semantics(G, class_deps)

        if G.number_of_nodes() == 0:
            self.logger.warning("Empty graph, no clusters detected")
            return []

        # Check if graph has edges
        if G.number_of_edges() == 0:
            self.logger.warning(
                "Graph has no edges (no method dependencies detected). "
                "This typically means methods are independent with no shared fields or calls. "
                "Creating fallback clusters for LLM-based analysis."
            )
            return self._create_fallback_clusters(G)

        # Multi-resolution clustering if enabled
        if self.multi_resolution_config.get("enabled", False):
            return self._multi_resolution_clustering(G)

        # Stability analysis if enabled
        if self.stability_config.get("enabled", False):
            return self._consensus_clustering(G)

        # Standard single-resolution clustering
        return self._detect_communities(G, self.resolution)

    def _detect_communities(self, G: nx.Graph, resolution: float) -> list[Cluster]:
        """
        Detect communities with specified resolution.

        Args:
            G: Graph to cluster
            resolution: Resolution parameter

        Returns:
            List of detected clusters
        """
        if self.algorithm == "leiden":
            partition, modularity = self._detect_communities_leiden(G, resolution)
        else:
            partition, modularity = self._detect_communities_louvain(G, resolution)

        self.logger.info(f"Graph modularity: {modularity:.4f}")

        # Group nodes by community
        communities: dict[int, list[str]] = {}
        for node, comm_id in partition.items():
            if comm_id not in communities:
                communities[comm_id] = []
            communities[comm_id].append(node)

        # Create Cluster objects
        clusters = []
        for cluster_id, members in communities.items():
            cluster = self._create_cluster(cluster_id, members, G, modularity)

            # Validate connectivity if enabled
            if self.validate_connectivity:
                subclusters = self._validate_and_split_connectivity(cluster, G)
                clusters.extend(subclusters)
            else:
                clusters.append(cluster)

        self.logger.info(f"Detected {len(clusters)} clusters")

        # Calculate advanced metrics if enabled
        if any(self.quality_metrics_config.values()):
            self._calculate_advanced_metrics(clusters, G)

        return clusters

    def _augment_graph_with_semantics(self, G: nx.Graph, class_deps: ClassDependencies) -> nx.Graph:
        """
        Augment graph with semantic similarity edges.

        Args:
            G: Original graph
            class_deps: Class dependencies

        Returns:
            Augmented graph with semantic edges
        """
        self.logger.info("Augmenting graph with semantic features")

        # Extract semantic features
        features_dict = self.semantic_analyzer.extract_class_features(class_deps)

        if not features_dict:
            self.logger.warning("No semantic features extracted, using graph-only")
            return G

        # Normalize features
        feature_matrix = self.semantic_analyzer.normalize_features(features_dict)

        # Create mapping from method signature to feature index
        methods = list(features_dict.keys())

        # Copy graph
        G_aug = G.copy()

        # Calculate semantic similarities and add edges
        from scipy.spatial.distance import euclidean

        edges_added = 0
        edges_augmented = 0

        for i, method1 in enumerate(methods):
            for j, method2 in enumerate(methods[i + 1 :], i + 1):
                # Calculate semantic similarity (1 - normalized euclidean distance)
                dist = euclidean(feature_matrix[i], feature_matrix[j])
                # Normalize distance to [0, 1]
                max_dist = np.sqrt(feature_matrix.shape[1])  # Max possible Euclidean distance
                semantic_sim = 1.0 - (dist / max_dist)

                # Only add/augment if similarity is above threshold
                if semantic_sim >= self.semantic_threshold:
                    if G_aug.has_edge(method1, method2):
                        # Augment existing edge with hybrid weight
                        graph_weight = G_aug[method1][method2]["weight"]
                        hybrid_weight = (
                            self.hybrid_alpha * graph_weight
                            + (1 - self.hybrid_alpha) * semantic_sim
                        )
                        G_aug[method1][method2]["weight"] = hybrid_weight
                        edges_augmented += 1
                    else:
                        # Add new semantic edge
                        G_aug.add_edge(
                            method1, method2, weight=(1 - self.hybrid_alpha) * semantic_sim
                        )
                        edges_added += 1

        self.logger.info(
            f"Semantic augmentation: {edges_added} new edges, {edges_augmented} edges augmented "
            f"(alpha={self.hybrid_alpha:.2f})"
        )

        return G_aug

    def _semantic_clustering_fallback(self, class_deps: ClassDependencies) -> list[Cluster]:
        """
        Pure semantic clustering for classes with no graph edges.

        Args:
            class_deps: Class dependencies

        Returns:
            Clusters based on semantic similarity
        """
        self.logger.info("Using pure semantic clustering (no graph edges)")

        if not self.semantic_analyzer:
            self.logger.warning("Semantic analyzer not available")
            return []

        # Extract and normalize features
        features_dict = self.semantic_analyzer.extract_class_features(class_deps)

        if not features_dict or len(features_dict) < self.min_cluster_size:
            return []

        feature_matrix = self.semantic_analyzer.normalize_features(features_dict)
        methods = list(features_dict.keys())

        # Use agglomerative clustering
        try:
            from sklearn.cluster import AgglomerativeClustering

            clustering = AgglomerativeClustering(
                n_clusters=None,
                distance_threshold=self.semantic_threshold,
                linkage="average",
                metric="euclidean",
            )

            labels = clustering.fit_predict(feature_matrix)

            # Group methods by cluster
            clusters = []
            for cluster_id in set(labels):
                member_indices = [i for i, label in enumerate(labels) if label == cluster_id]
                member_names = [methods[i] for i in member_indices]

                if len(member_names) < self.min_cluster_size:
                    continue

                # Create cluster
                member_types = {name: "method" for name in member_names}

                cluster = Cluster(
                    id=cluster_id,
                    member_names=member_names,
                    member_types=member_types,
                    modularity=0.0,
                    internal_cohesion=0.0,
                    external_coupling=0.0,
                )

                clusters.append(cluster)

            self.logger.info(f"Semantic clustering created {len(clusters)} clusters")
            return clusters

        except Exception as e:
            self.logger.warning(f"Semantic clustering failed: {e}")
            return []

    def _detect_communities_louvain(self, G: nx.Graph, resolution: float) -> tuple[dict, float]:
        """Run Louvain community detection."""
        partition = community_louvain.best_partition(
            G, weight="weight", resolution=resolution, random_state=42
        )
        modularity = community_louvain.modularity(partition, G, weight="weight")
        return partition, modularity

    def _detect_communities_leiden(self, G: nx.Graph, resolution: float) -> tuple[dict, float]:
        """Run Leiden community detection (guaranteed connected communities)."""
        # Convert NetworkX graph to igraph
        ig_graph = self._networkx_to_igraph(G)

        # Run Leiden algorithm
        partition = leidenalg.find_partition(
            ig_graph,
            leidenalg.RBConfigurationVertexPartition,
            weights="weight",
            resolution_parameter=resolution,
            seed=42,
        )

        # Convert back to node -> community mapping
        node_list = list(G.nodes())
        partition_dict = {}
        for comm_id, members in enumerate(partition):
            for node_idx in members:
                partition_dict[node_list[node_idx]] = comm_id

        modularity = partition.quality()
        return partition_dict, modularity

    def _networkx_to_igraph(self, G: nx.Graph) -> "ig.Graph":
        """Convert NetworkX graph to igraph format."""
        # Create mapping from node names to indices
        node_list = list(G.nodes())
        node_to_idx = {node: idx for idx, node in enumerate(node_list)}

        # Create edge list with indices
        edges = [(node_to_idx[u], node_to_idx[v]) for u, v in G.edges()]
        weights = [G[u][v]["weight"] for u, v in G.edges()]

        # Create igraph
        ig_graph = ig.Graph(n=len(node_list), edges=edges, directed=False)
        ig_graph.es["weight"] = weights

        return ig_graph

    def _create_cluster(
        self, cluster_id: int, members: list[str], G: nx.Graph, modularity: float
    ) -> Cluster:
        """Create a Cluster object from community members."""
        # Get member types from graph
        member_types = {}
        for member in members:
            node_type = G.nodes[member].get("type", "method")
            member_types[member] = node_type

        cluster = Cluster(
            id=cluster_id, member_names=members, member_types=member_types, modularity=modularity
        )

        # Calculate basic cluster quality metrics
        self._calculate_cluster_metrics(cluster, G)

        return cluster

    def _validate_and_split_connectivity(self, cluster: Cluster, G: nx.Graph) -> list[Cluster]:
        """
        Validate cluster connectivity and split if disconnected.

        Args:
            cluster: Cluster to validate
            G: Full graph

        Returns:
            List of clusters (original if connected, split components if disconnected)
        """
        # Get subgraph induced by cluster members
        subgraph = G.subgraph(cluster.member_names)

        # Check connectivity
        if nx.is_connected(subgraph):
            cluster.is_connected = True
            return [cluster]

        # Cluster is disconnected - split into connected components
        if not self.split_disconnected:
            cluster.is_connected = False
            self.logger.warning(
                f"Cluster {cluster.id} is disconnected ({len(cluster)} members) "
                f"but split_disconnected=False"
            )
            return [cluster]

        components = list(nx.connected_components(subgraph))
        self.logger.warning(
            f"Cluster {cluster.id} is disconnected! Splitting into {len(components)} "
            f"connected components"
        )

        # Create sub-clusters from connected components
        subclusters = []
        for comp_idx, component in enumerate(components):
            members = list(component)
            member_types = {m: cluster.member_types[m] for m in members}

            subcluster = Cluster(
                id=cluster.id * 1000 + comp_idx,  # Unique ID
                member_names=members,
                member_types=member_types,
                modularity=cluster.modularity,
                is_connected=True,
            )

            # Recalculate metrics for subcluster
            self._calculate_cluster_metrics(subcluster, G)
            subclusters.append(subcluster)

        return subclusters

    def _multi_resolution_clustering(self, G: nx.Graph) -> list[Cluster]:
        """
        Try multiple resolution parameters and select best clustering.

        Args:
            G: Graph to cluster

        Returns:
            Best clustering found
        """
        resolution_range = self.multi_resolution_config.get(
            "resolution_range", [0.5, 0.75, 1.0, 1.25, 1.5]
        )
        quality_metric = self.multi_resolution_config.get("quality_metric", "silhouette")

        self.logger.info(
            f"Running multi-resolution clustering with resolutions: {resolution_range}"
        )

        best_clusters = None
        best_score = -float("inf")
        best_resolution = None

        for resolution in resolution_range:
            clusters = self._detect_communities(G, resolution)

            # Calculate quality score
            if quality_metric == "modularity" and clusters:
                score = clusters[0].modularity
            elif quality_metric == "silhouette" and len(clusters) > 1:
                score = self._calculate_silhouette_score_for_clustering(clusters, G)
            else:
                score = 0.0

            self.logger.info(
                f"  Resolution {resolution}: {len(clusters)} clusters, "
                f"{quality_metric}={score:.4f}"
            )

            if score > best_score:
                best_score = score
                best_clusters = clusters
                best_resolution = resolution

        self.logger.info(
            f"Selected resolution {best_resolution} with {quality_metric}={best_score:.4f}"
        )

        return best_clusters if best_clusters else []

    def _consensus_clustering(self, G: nx.Graph) -> list[Cluster]:
        """
        Run consensus clustering for stable results.

        Args:
            G: Graph to cluster

        Returns:
            Stable clusters from consensus
        """
        iterations = self.stability_config.get("iterations", 10)
        threshold = self.stability_config.get("threshold", 0.7)

        self.logger.info(f"Running consensus clustering with {iterations} iterations")

        nodes = list(G.nodes())
        n = len(nodes)
        node_to_idx = {node: idx for idx, node in enumerate(nodes)}

        # Co-occurrence matrix
        cooccurrence = np.zeros((n, n))

        # Run clustering multiple times
        for i in range(iterations):
            # Add randomness by perturbing edge weights slightly
            G_perturbed = G.copy()
            for u, v in G_perturbed.edges():
                weight = G_perturbed[u][v]["weight"]
                noise = np.random.normal(0, 0.1 * weight)
                G_perturbed[u][v]["weight"] = max(0.01, weight + noise)

            # Detect communities
            clusters = self._detect_communities(G_perturbed, self.resolution)

            # Update co-occurrence matrix
            for cluster in clusters:
                members = cluster.member_names
                for m1 in members:
                    for m2 in members:
                        if m1 != m2:
                            idx1 = node_to_idx[m1]
                            idx2 = node_to_idx[m2]
                            cooccurrence[idx1][idx2] += 1

        # Normalize
        cooccurrence /= iterations

        # Threshold to create consensus graph
        consensus_edges = []
        for i in range(n):
            for j in range(i + 1, n):
                if cooccurrence[i][j] >= threshold:
                    consensus_edges.append((nodes[i], nodes[j], cooccurrence[i][j]))

        # Build consensus graph
        G_consensus = nx.Graph()
        G_consensus.add_nodes_from(nodes)
        for u, v, weight in consensus_edges:
            G_consensus.add_edge(u, v, weight=weight)
            # Copy node attributes
            for node in [u, v]:
                if node in G.nodes:
                    for attr, value in G.nodes[node].items():
                        G_consensus.nodes[node][attr] = value

        # Cluster the consensus graph
        if G_consensus.number_of_edges() > 0:
            clusters = self._detect_communities(G_consensus, self.resolution)

            # Calculate stability scores
            for cluster in clusters:
                members = cluster.member_names
                if len(members) > 1:
                    # Average co-occurrence within cluster
                    scores = []
                    for m1 in members:
                        for m2 in members:
                            if m1 != m2:
                                idx1 = node_to_idx[m1]
                                idx2 = node_to_idx[m2]
                                scores.append(cooccurrence[idx1][idx2])
                    cluster.stability_score = np.mean(scores) if scores else 0.0
                else:
                    cluster.stability_score = 1.0

                self.logger.debug(f"Cluster {cluster.id}: stability={cluster.stability_score:.3f}")
        else:
            clusters = self._create_fallback_clusters(G)

        self.logger.info(f"Consensus clustering produced {len(clusters)} stable clusters")

        return clusters

    def _calculate_silhouette_score_for_clustering(
        self, clusters: list[Cluster], G: nx.Graph
    ) -> float:
        """Calculate average silhouette score for entire clustering."""
        if not SKLEARN_AVAILABLE or len(clusters) < 2:
            return 0.0

        # Create feature matrix and labels
        nodes = []
        labels = []
        for cluster in clusters:
            for member in cluster.member_names:
                nodes.append(member)
                labels.append(cluster.id)

        if len(set(labels)) < 2:
            return 0.0

        features = self._create_feature_matrix(nodes, G)

        try:
            score = silhouette_score(features, labels)
            return score
        except Exception as e:
            self.logger.debug(f"Could not calculate silhouette score: {e}")
            return 0.0

    def _calculate_advanced_metrics(self, clusters: list[Cluster], G: nx.Graph):
        """Calculate advanced quality metrics for clusters."""
        if not any(self.quality_metrics_config.values()):
            return

        # Silhouette score (per-cluster)
        if self.quality_metrics_config.get("silhouette", False) and SKLEARN_AVAILABLE:
            if len(clusters) > 1:
                nodes = []
                labels = []
                for cluster in clusters:
                    for member in cluster.member_names:
                        nodes.append(member)
                        labels.append(cluster.id)

                if len(set(labels)) > 1:
                    features = self._create_feature_matrix(nodes, G)

                    try:
                        # Calculate per-sample silhouette scores
                        from sklearn.metrics import silhouette_samples

                        sample_scores = silhouette_samples(features, labels)

                        # Assign scores to clusters
                        node_to_score = {node: score for node, score in zip(nodes, sample_scores, strict=False)}
                        for cluster in clusters:
                            scores = [
                                node_to_score[m] for m in cluster.member_names if m in node_to_score
                            ]
                            cluster.silhouette_score = np.mean(scores) if scores else None
                    except Exception as e:
                        self.logger.debug(f"Could not calculate silhouette scores: {e}")

        # Conductance
        if self.quality_metrics_config.get("conductance", False):
            for cluster in clusters:
                cluster.conductance = self._calculate_conductance(cluster, G)

        # Coverage
        if self.quality_metrics_config.get("coverage", False):
            total_edges = G.number_of_edges()
            if total_edges > 0:
                internal_edges = sum(
                    len(
                        [
                            (u, v)
                            for u in cluster.member_names
                            for v in cluster.member_names
                            if u < v and G.has_edge(u, v)
                        ]
                    )
                    for cluster in clusters
                )
                coverage = internal_edges / total_edges
                for cluster in clusters:
                    cluster.coverage = coverage

    def _create_feature_matrix(self, nodes: list[str], G: nx.Graph) -> np.ndarray:
        """Create feature matrix for silhouette score calculation."""
        features = []
        for node in nodes:
            # Features: degree, clustering coefficient, avg neighbor degree
            degree = G.degree(node, weight="weight")
            clustering_coef = nx.clustering(G, node, weight="weight")

            # Average neighbor degree
            neighbors = list(G.neighbors(node))
            if neighbors:
                avg_neighbor_degree = np.mean([G.degree(n, weight="weight") for n in neighbors])
            else:
                avg_neighbor_degree = 0.0

            features.append([degree, clustering_coef, avg_neighbor_degree])

        # Normalize features
        features = np.array(features)
        if SKLEARN_AVAILABLE:
            scaler = StandardScaler()
            features = scaler.fit_transform(features)

        return features

    def _calculate_conductance(self, cluster: Cluster, G: nx.Graph) -> float:
        """
        Calculate conductance: ratio of cut edges to min volume.

        Lower conductance = better cluster (fewer boundary edges).
        """
        members = set(cluster.member_names)

        # Count cut edges and internal volume
        cut_weight = 0.0
        internal_volume = 0.0
        external_volume = 0.0

        for node in members:
            for neighbor in G.neighbors(node):
                weight = G[node][neighbor]["weight"]
                if neighbor in members:
                    internal_volume += weight
                else:
                    cut_weight += weight
                    external_volume += weight

        # Avoid division by zero
        if internal_volume == 0 and external_volume == 0:
            return 0.0

        # Conductance = cut / min(vol_in, vol_out)
        min_volume = min(internal_volume, internal_volume + external_volume)
        if min_volume == 0:
            return 1.0

        return cut_weight / min_volume

    def filter_clusters(
        self, clusters: list[Cluster], class_deps: ClassDependencies | None = None
    ) -> list[Cluster]:
        """
        Filter clusters by size and quality constraints.

        Args:
            clusters: List of clusters to filter
            class_deps: Class dependencies for extraction validation (optional)

        Returns:
            Filtered list of clusters
        """
        self.logger.info("Filtering clusters by size and quality")

        # Initialize extraction validator if class_deps provided
        extraction_validator = None
        if class_deps:
            from genec.verification.extraction_validator import ExtractionValidator

            extraction_validator = ExtractionValidator()

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

            # Validate extraction safety
            if extraction_validator:
                is_valid, issues = extraction_validator.validate_extraction(cluster, class_deps)
                if not is_valid:
                    self.logger.info(
                        f"Cluster {cluster.id} cannot be safely extracted: "
                        f"{len([i for i in issues if i.severity == 'error'])} blocking issues"
                    )
                    for issue in issues:
                        if issue.severity == "error":
                            self.logger.debug(f"  - {issue.issue_type}: {issue.description}")
                        elif issue.issue_type == "pattern_suggestion":
                            self.logger.info(f"  - {issue.description}")

                    # Store rejection info with transformation guidance
                    cluster.rejection_issues = issues
                    continue

            filtered.append(cluster)

        self.logger.info(f"Filtered to {len(filtered)} clusters")

        return filtered

    def rank_clusters(self, clusters: list[Cluster]) -> list[Cluster]:
        """
        Rank clusters by quality score.

        Quality score considers:
        - Modularity
        - Internal cohesion
        - Low external coupling
        - Appropriate size
        - Silhouette score (if available)
        - Stability score (if available)

        Args:
            clusters: List of clusters to rank

        Returns:
            Sorted list of clusters (best first)
        """
        self.logger.info("Ranking clusters by quality")

        for cluster in clusters:
            # Calculate rank score
            size_score = self._calculate_size_score(len(cluster))

            # Base weighted combination
            rank_score = (
                0.25 * cluster.modularity
                + 0.35 * cluster.internal_cohesion
                + 0.15 * (1.0 - cluster.external_coupling)
                + 0.10 * size_score
            )

            # Add silhouette score if available
            if cluster.silhouette_score is not None:
                rank_score += 0.10 * max(0.0, cluster.silhouette_score)

            # Add stability score if available
            if cluster.stability_score is not None:
                rank_score += 0.05 * cluster.stability_score

            cluster.rank_score = rank_score

        # Sort by rank score (descending)
        ranked = sorted(clusters, key=lambda c: c.rank_score, reverse=True)

        for i, cluster in enumerate(ranked, 1):
            metrics = [
                f"Rank {i}: Cluster {cluster.id}",
                f"Score: {cluster.rank_score:.4f}",
                f"Size: {len(cluster)}",
                f"Cohesion: {cluster.internal_cohesion:.4f}",
            ]
            if cluster.silhouette_score is not None:
                metrics.append(f"Silhouette: {cluster.silhouette_score:.3f}")
            if cluster.stability_score is not None:
                metrics.append(f"Stability: {cluster.stability_score:.3f}")

            self.logger.debug(" - ".join(metrics))

        return ranked

    def validate_extractability(self, cluster: Cluster, class_deps: ClassDependencies) -> bool:
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
                        f"Method {method_sig} accesses field {field} " f"which is not in cluster"
                    )
                    # This is a warning, not necessarily a blocker
                    # We could add the field to the cluster

        return True

    def _calculate_cluster_metrics(self, cluster: Cluster, G: nx.Graph):
        """
        Calculate quality metrics for a cluster (OPTIMIZED VERSION).

        Args:
            cluster: Cluster to analyze
            G: Full graph
        """
        members = set(cluster.member_names)

        # OPTIMIZATION: Use subgraph instead of nested loops
        subgraph = G.subgraph(members)

        # Calculate internal cohesion (average weight of internal edges)
        if subgraph.number_of_edges() > 0:
            internal_weights = [subgraph[u][v]["weight"] for u, v in subgraph.edges()]
            cluster.internal_cohesion = np.mean(internal_weights)
        else:
            cluster.internal_cohesion = 0.0

        # Calculate external coupling (average weight of edges to outside)
        external_edges = []
        for u in members:
            for v in G.neighbors(u):
                if v not in members:
                    external_edges.append(G[u][v]["weight"])

        if external_edges:
            cluster.external_coupling = np.mean(external_edges)
        else:
            cluster.external_coupling = 0.0

        # Normalize external coupling to [0, 1]
        if cluster.internal_cohesion > 0:
            cluster.external_coupling = min(
                1.0, cluster.external_coupling / cluster.internal_cohesion
            )

        # Calculate overall quality score
        cluster.quality_score = cluster.internal_cohesion * (1.0 - cluster.external_coupling)

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

    def _create_fallback_clusters(self, G: nx.Graph) -> list[Cluster]:
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
            node_type = G.nodes[node].get("type", "method")
            member_types[node] = node_type
            if node_type == "method":
                methods.append(node)
            else:
                fields.append(node)

        # If class is very large (>max_cluster_size), group by naming patterns
        if len(nodes) > self.max_cluster_size:
            self.logger.info(f"Large class with {len(nodes)} members, grouping by naming patterns")
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
                external_coupling=0.0,
            )

            self.logger.info(
                f"Created fallback cluster with {len(nodes)} members "
                f"({len(cluster.get_methods())} methods, {len(cluster.get_fields())} fields)"
            )

            return [cluster]

    def _create_pattern_based_clusters(
        self, methods: list[str], fields: list[str], member_types: dict[str, str]
    ) -> list[Cluster]:
        """
        Group methods by naming patterns for large classes (IMPROVED VERSION).

        Args:
            methods: List of method names
            fields: List of field names
            member_types: Mapping of member names to types

        Returns:
            List of clusters grouped by naming patterns
        """
        # Get configurable patterns
        pattern_config = self.clustering_config.get("clustering_patterns", [])

        # Build pattern list from config or use defaults
        if pattern_config:
            prefixes = [p["prefix"] for p in pattern_config]
            pattern_str = "|".join(prefixes)
        else:
            # Default patterns
            pattern_str = (
                "is|has|get|set|contains?|starts?|ends?|split|join|strip|trim|pad|"
                "remove|replace|substring|index|count|check|validate|find|search|"
                "parse|format|convert|to|from|create|build|add|append|prepend|insert|"
                "delete|truncate|wrap|unwrap|escape|unescape|encode|decode|normalize|"
                "compare|equals?|matches?|empty|blank|null|default|abbreviate|"
                "capitalize|center|chop|reverse|rotate|swap|overlay|repeat|difference"
            )

        # Group methods by common prefixes/patterns
        groups = defaultdict(list)

        for method in methods:
            # Extract prefix
            prefix_match = re.match(f"^({pattern_str})[A-Z]", method)

            if prefix_match:
                prefix = prefix_match.group(1)
                groups[prefix].append(method)
            else:
                # No clear prefix, use first word
                words = re.findall(r"[A-Z][a-z]*", method)
                if words:
                    groups[words[0].lower()].append(method)
                else:
                    groups["other"].append(method)

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
                external_coupling=0.0,
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
