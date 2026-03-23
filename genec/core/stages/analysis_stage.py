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
            class_deps = self.dependency_analyzer.analyze_class(class_file)
            if not class_deps:
                self.logger.error(f"Dependency analysis returned no data for {class_file}")
                return False
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

        # Build method name/signature mapping for evolutionary graph
        method_map: dict[str, str | list[str]] = {}
        for m in class_deps.get_all_methods():
            existing = method_map.get(m.name)
            if isinstance(existing, list):
                if m.signature not in existing:
                    existing.append(m.signature)
            elif existing is None:
                method_map[m.name] = [m.signature]

            method_map[m.signature] = m.signature
            for variant in self._signature_variants(m.signature):
                method_map.setdefault(variant, m.signature)
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

        # Build conceptual similarity graph if beta > 0
        G_conceptual = None
        beta = fusion_config.get("beta", 0.0)
        if beta > 0:
            try:
                from genec.core.conceptual_analyzer import build_conceptual_graph
                conceptual_min_sim = fusion_config.get("conceptual_min_similarity", 0.1)
                G_conceptual = build_conceptual_graph(
                    class_deps.get_all_methods(),
                    min_similarity=conceptual_min_sim,
                )
                self.logger.info(
                    f"Conceptual graph: {G_conceptual.number_of_nodes()} nodes, "
                    f"{G_conceptual.number_of_edges()} edges"
                )
            except Exception as e:
                self.logger.warning(f"Failed to build conceptual graph: {e}")
                G_conceptual = None

        G_fused = self.graph_builder.fuse_graphs(
            G_static,
            G_evo,
            alpha=fusion_config.get("alpha", 0.5),
            edge_threshold=fusion_config.get("edge_threshold", 0.1),
            hotspot_data=hotspot_data,
            adaptive_fusion=adaptive_fusion,
            G_conceptual=G_conceptual,
            beta=beta,
        )

        context.set("G_fused", G_fused)
        context.results["fused_graph"] = G_fused

        if context.recorder:
            context.recorder.end_stage("analysis", {
                "methods_found": len(class_deps.methods) if class_deps.methods else 0,
                "fields_found": len(class_deps.fields) if class_deps.fields else 0,
                "method_calls_count": sum(len(v) for v in class_deps.method_calls.values()) if class_deps.method_calls else 0,
                "field_accesses_count": sum(len(v) for v in class_deps.field_accesses.values()) if class_deps.field_accesses else 0,
                "commits_analyzed": getattr(evo_data, 'total_commits', 0),
                "co_changes_found": len(getattr(evo_data, 'co_changes', {})),
                "graph_nodes": G_fused.number_of_nodes() if G_fused else 0,
                "graph_edges": G_fused.number_of_edges() if G_fused else 0,
            })

        return True

    @staticmethod
    def _signature_variants(signature: str) -> set[str]:
        """
        Generate normalized variants of a method signature to improve matching
        between evolutionary mining and static analysis.
        """
        import re

        if not signature:
            return set()

        variants = {signature}

        # Remove whitespace
        compact = re.sub(r"\s+", "", signature)
        variants.add(compact)

        # Strip generic parameters within types
        no_generics = re.sub(r"<[^>]*>", "", compact)
        variants.add(no_generics)

        # Normalize varargs and arrays
        variants.add(no_generics.replace("...", "[]"))
        variants.add(no_generics.replace("[]", "..."))

        # Add variant with arrays stripped (fallback for parsers that omit [])
        variants.add(no_generics.replace("[]", ""))

        return {v for v in variants if v}
