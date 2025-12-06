from genec.core.llm_interface import LLMInterface
from genec.core.stages.base_stage import PipelineContext, PipelineStage
from genec.utils.progress_server import emit_progress


class NamingStage(PipelineStage):
    """Stage for generating refactoring suggestions with LLM naming."""

    def __init__(self, llm_interface: LLMInterface):
        super().__init__("Naming")
        self.llm_interface = llm_interface

    def run(self, context: PipelineContext) -> bool:
        emit_progress(5, 6, "Generating suggestions...")
        self.logger.info("Generating refactoring suggestions...")

        ranked_clusters = context.get("ranked_clusters")
        class_deps = context.get("class_deps")
        evo_data = context.get("evo_data")
        repo_path = context.repo_path
        class_file = context.class_file

        if not ranked_clusters:
            self.logger.warning("No clusters found to name")
            context.results["suggestions"] = []
            return True

        try:
            with open(class_file, encoding="utf-8") as f:
                original_code = f.read()
        except Exception as e:
            self.logger.error(f"Failed to read class file {class_file}: {e}")
            return False

        max_suggestions = context.config.get("max_suggestions")

        # Filter clusters based on quality tiers if needed
        # For now, we pass all ranked clusters

        suggestions = self.llm_interface.generate_batch_suggestions(
            clusters=ranked_clusters,
            original_code=original_code,
            class_deps=class_deps,
            class_file=class_file,
            repo_path=repo_path,
            evo_data=evo_data,
        )

        if max_suggestions and len(suggestions) > max_suggestions:
            suggestions = suggestions[:max_suggestions]

        context.set("suggestions", suggestions)
        context.results["suggestions"] = suggestions

        self.logger.info(f"Generated {len(suggestions)} refactoring suggestions")
        return True
