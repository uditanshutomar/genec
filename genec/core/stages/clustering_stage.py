from genec.core.cluster_detector import ClusterDetector, calculate_quality_tier
from genec.core.stages.base_stage import PipelineContext, PipelineStage
from genec.utils.progress_server import emit_progress


class ClusteringStage(PipelineStage):
    """Stage for detecting and ranking clusters."""

    def __init__(self, cluster_detector: ClusterDetector):
        super().__init__("Clustering")
        self.cluster_detector = cluster_detector

    def run(self, context: PipelineContext) -> bool:
        emit_progress(4, 6, "Detecting clusters...")
        self.logger.info("Detecting and ranking clusters...")

        G_fused = context.get("G_fused")
        class_deps = context.get("class_deps")
        evo_data = context.get("evo_data")

        if not G_fused or not class_deps:
            self.logger.error("Missing graph or dependency data")
            return False

        all_clusters = self.cluster_detector.detect_clusters(G_fused, class_deps)
        context.results["all_clusters"] = all_clusters

        # Calculate quality tiers for all clusters
        for cluster in all_clusters:
            calculate_quality_tier(cluster, evo_data)

        # Pass class_deps to enable extraction validation
        filtered_clusters = self.cluster_detector.filter_clusters(all_clusters, class_deps)
        context.results["filtered_clusters"] = filtered_clusters

        # Capture rejected clusters for downstream structural planning
        rejected_clusters = [c for c in all_clusters if getattr(c, "rejection_issues", None)]
        context.results["rejected_clusters"] = rejected_clusters
        context.set("rejected_clusters", rejected_clusters)

        ranked_clusters = self.cluster_detector.rank_clusters(filtered_clusters)
        context.results["ranked_clusters"] = ranked_clusters

        context.set("ranked_clusters", ranked_clusters)

        self.logger.info(f"Found {len(ranked_clusters)} candidate clusters")

        if context.recorder:
            context.recorder.end_stage("clustering", {
                "clusters_total": len(all_clusters),
                "clusters_filtered": len(filtered_clusters),
                "clusters_ranked": len(ranked_clusters),
                "clusters_rejected": len(rejected_clusters),
                "avg_cohesion": sum(getattr(c, 'cohesion', 0) for c in ranked_clusters) / max(len(ranked_clusters), 1),
            })

        return True
