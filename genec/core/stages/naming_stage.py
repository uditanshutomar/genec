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

        # Filter by confidence threshold if configured
        min_confidence = context.config.get("naming", {}).get("min_confidence_threshold", 0.0)
        if min_confidence > 0.0:
            original_count = len(suggestions)
            suggestions = [
                s for s in suggestions
                if s.confidence_score is None or s.confidence_score >= min_confidence
            ]
            filtered_count = original_count - len(suggestions)
            if filtered_count > 0:
                self.logger.info(
                    f"Filtered out {filtered_count} low-confidence suggestions "
                    f"(threshold: {min_confidence})"
                )

        # Sort by confidence score (highest first)
        sort_by_confidence = context.config.get("naming", {}).get("sort_by_confidence", True)
        if sort_by_confidence:
            suggestions.sort(key=lambda s: s.confidence_score or 0.0, reverse=True)
            self.logger.info("Sorted suggestions by confidence score (highest first)")

        if max_suggestions and len(suggestions) > max_suggestions:
            suggestions = suggestions[:max_suggestions]

        context.set("suggestions", suggestions)
        context.results["suggestions"] = suggestions

        # Log confidence statistics
        if suggestions:
            confidence_scores = [s.confidence_score for s in suggestions if s.confidence_score is not None]
            if confidence_scores:
                avg_confidence = sum(confidence_scores) / len(confidence_scores)
                max_conf = max(confidence_scores)
                min_conf = min(confidence_scores)
                self.logger.info(
                    f"Generated {len(suggestions)} suggestions "
                    f"(confidence: avg={avg_confidence:.2f}, min={min_conf:.2f}, max={max_conf:.2f})"
                )
            else:
                self.logger.info(f"Generated {len(suggestions)} refactoring suggestions")
        else:
            self.logger.warning("No suggestions passed confidence filtering")

        return True
