from pathlib import Path

from networkx.readwrite import json_graph

from genec.core.graph_builder import GraphBuilder
from genec.core.stages.base_stage import PipelineContext, PipelineStage


class GraphProcessingStage(PipelineStage):
    """Stage for calculating graph metrics and exporting graphs."""

    def __init__(self, graph_builder: GraphBuilder):
        super().__init__("GraphProcessing")
        self.graph_builder = graph_builder

    def run(self, context: PipelineContext) -> bool:
        G_fused = context.get("G_fused")
        class_deps = context.get("class_deps")

        if not G_fused:
            self.logger.warning("No fused graph found, skipping processing")
            return True

        fusion_config = context.config.get("fusion", {})

        # Calculate centrality metrics
        centrality_config = fusion_config.get("centrality", {})
        if centrality_config.get("enabled", True):
            top_n = centrality_config.get("top_n", 10)
            centrality_metrics = self.graph_builder.calculate_centrality_metrics(
                G_fused, top_n=top_n
            )

            # Add to graph nodes if requested
            if centrality_config.get("add_to_graph", True):
                G_fused = self.graph_builder.add_centrality_to_graph(G_fused, centrality_metrics)

            context.results["centrality_metrics"] = centrality_metrics
            self.logger.info(f"Calculated {len(centrality_metrics)} centrality metrics")

        # Calculate graph metrics
        graph_metrics = self.graph_builder.get_graph_metrics(G_fused)
        context.results["graph_metrics"] = graph_metrics
        self.logger.info(f"Graph metrics: {graph_metrics}")

        # Generate graph data for JSON output
        # NetworkX 3.x uses 'link' parameter instead of 'edges'
        try:
            # NetworkX 3.x API
            context.results["graph_data"] = json_graph.node_link_data(G_fused, link="links")
        except TypeError:
            # Fallback for older NetworkX versions (< 3.0)
            try:
                context.results["graph_data"] = json_graph.node_link_data(G_fused, edges="links")
            except TypeError:
                # Last resort - use default parameters
                context.results["graph_data"] = json_graph.node_link_data(G_fused)

        # Export graph if requested
        export_config = fusion_config.get("export", {})
        if export_config.get("enabled", False):
            output_dir = Path(export_config.get("output_dir", "output/graphs"))
            output_dir.mkdir(parents=True, exist_ok=True)

            class_name = class_deps.class_name if class_deps else "unknown"
            formats = export_config.get("formats", ["graphml", "json"])

            for fmt in formats:
                try:
                    output_file = output_dir / f"{class_name}_fused.{fmt}"
                    self.graph_builder.export_graph(G_fused, str(output_file), format=fmt)
                    self.logger.info(f"Exported graph to {output_file}")
                except Exception as e:
                    self.logger.warning(f"Failed to export graph as {fmt}: {e}")

            # Export centrality metrics if calculated
            if "centrality_metrics" in context.results:
                centrality_file = output_dir / f"{class_name}_centrality.json"
                try:
                    self.graph_builder.export_centrality_metrics(
                        context.results["centrality_metrics"], str(centrality_file), format="json"
                    )
                    self.logger.info(f"Exported centrality metrics to {centrality_file}")
                except Exception as e:
                    self.logger.warning(f"Failed to export centrality metrics: {e}")

        return True
