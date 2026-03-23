from unittest.mock import MagicMock, patch
from genec.core.stages.clustering_stage import ClusteringStage
from genec.core.stages.base_stage import PipelineContext


class TestClusteringStageUnit:
    def test_returns_false_without_graph(self):
        detector = MagicMock()
        stage = ClusteringStage(detector)
        ctx = PipelineContext(config={}, repo_path="/tmp", class_file="/tmp/T.java")
        assert stage.run(ctx) is False

    @patch("genec.core.stages.clustering_stage.calculate_quality_tier")
    def test_stores_ranked_clusters(self, mock_quality_tier):
        cluster1 = MagicMock(cohesion=0.8, rejection_issues=None)
        cluster2 = MagicMock(cohesion=0.5, rejection_issues=None)

        detector = MagicMock()
        detector.detect_clusters.return_value = [cluster1, cluster2]
        detector.filter_clusters.return_value = [cluster1, cluster2]
        detector.rank_clusters.return_value = [cluster1, cluster2]

        stage = ClusteringStage(detector)
        ctx = PipelineContext(config={}, repo_path="/tmp", class_file="/tmp/T.java")
        ctx.set("G_fused", MagicMock())
        ctx.set("class_deps", MagicMock())
        ctx.set("evo_data", MagicMock())

        result = stage.run(ctx)
        assert result is True
        assert len(ctx.results["ranked_clusters"]) == 2

    @patch("genec.core.stages.clustering_stage.calculate_quality_tier")
    def test_captures_rejected_clusters(self, mock_quality_tier):
        good = MagicMock(cohesion=0.8, rejection_issues=None)
        bad = MagicMock(cohesion=0.1, rejection_issues=["too small"])

        detector = MagicMock()
        detector.detect_clusters.return_value = [good, bad]
        detector.filter_clusters.return_value = [good]
        detector.rank_clusters.return_value = [good]

        stage = ClusteringStage(detector)
        ctx = PipelineContext(config={}, repo_path="/tmp", class_file="/tmp/T.java")
        ctx.set("G_fused", MagicMock())
        ctx.set("class_deps", MagicMock())
        ctx.set("evo_data", MagicMock())

        stage.run(ctx)
        assert len(ctx.results["rejected_clusters"]) == 1
