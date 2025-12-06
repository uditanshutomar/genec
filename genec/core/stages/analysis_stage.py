from pathlib import Path

from genec.core.dependency_analyzer import DependencyAnalyzer
from genec.core.evolutionary_miner import EvolutionaryMiner
from genec.core.graph_builder import GraphBuilder
from genec.core.stages.base_stage import PipelineContext, PipelineStage
from genec.utils.progress_server import emit_progress


class AnalysisStage(PipelineStage):
    """Stage for analyzing code and building dependency graphs."""

    def __init__(
        self,
        dependency_analyzer: DependencyAnalyzer,
        evolutionary_miner: EvolutionaryMiner,
        graph_builder: GraphBuilder,
    ):
        super().__init__("Analysis")
        self.dependency_analyzer = dependency_analyzer
        self.evolutionary_miner = evolutionary_miner
        self.graph_builder = graph_builder

    def run(self, context: PipelineContext) -> bool:
        class_file = context.class_file
        repo_path = context.repo_path

        emit_progress(1, 6, "Analyzing dependencies...")
        self.logger.info(f"Analyzing dependencies for {class_file}...")

        # Stage 1: Dependency Analysis
        try:
            class_deps = self.dependency_analyzer.analyze(class_file)
            context.set("class_deps", class_deps)
            context.results["class_dependencies"] = class_deps
        except Exception as e:
            self.logger.error(f"Dependency analysis failed: {e}")
            return False

        # Stage 2: Evolutionary Mining
        emit_progress(2, 6, "Mining evolutionary coupling...")
        self.logger.info("Mining evolutionary coupling from Git history...")

        evo_config = context.config.get("evolution", {})

        # Convert absolute path to relative path from repo root
        class_file_path = Path(class_file).resolve()
        repo_path_obj = Path(repo_path).resolve()

        try:
            relative_path = class_file_path.relative_to(repo_path_obj)
            relative_path_str = str(relative_path)
        except ValueError:
            self.logger.warning(f"Class file {class_file} is not in repo {repo_path}")
            relative_path_str = class_file

        evo_data = self.evolutionary_miner.mine_method_cochanges(
            relative_path_str,
            repo_path,
            window_months=evo_config.get("window_months", 120),
            min_commits=evo_config.get("min_commits", 2),
        )
        context.set("evo_data", evo_data)
        context.results["evolutionary_data"] = evo_data

        # Stage 3: Graph Building
        emit_progress(3, 6, "Building dependency graphs...")
        self.logger.info("Building and fusing dependency graphs...")

        G_static = self.graph_builder.build_static_graph(class_deps)

        # Build method name to signature mapping for evolutionary graph
        method_map = {m.name: m.signature for m in class_deps.get_all_methods()}
        G_evo = self.graph_builder.build_evolutionary_graph(evo_data, method_map)

        fusion_config = context.config.get("fusion", {})

        # Get hotspot data for adaptive fusion
        hotspot_data = None
        adaptive_fusion = fusion_config.get("adaptive_fusion", False)
        if adaptive_fusion and evo_data.method_names:
            try:
                hotspot_data = self.evolutionary_miner.get_method_hotspots(
                    evo_data, top_n=len(evo_data.method_names)
                )
                self.logger.info(f"Using adaptive fusion with {len(hotspot_data)} hotspot scores")
            except Exception as e:
                self.logger.warning(f"Failed to calculate hotspots: {e}")
                hotspot_data = None

        G_fused = self.graph_builder.fuse_graphs(
            G_static,
            G_evo,
            alpha=fusion_config.get("alpha", 0.5),
            edge_threshold=fusion_config.get("edge_threshold", 0.1),
            hotspot_data=hotspot_data,
            adaptive_fusion=adaptive_fusion,
        )

        context.set("G_fused", G_fused)
        context.results["fused_graph"] = G_fused

        return True
