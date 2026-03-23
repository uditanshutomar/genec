import re

from genec.core.cluster_detector import Cluster
from genec.core.dependency_analyzer import ClassDependencies
from genec.core.llm_interface import LLMInterface, RefactoringSuggestion
from genec.core.stages.base_stage import PipelineContext, PipelineStage
from genec.utils.progress_server import emit_progress


def _auto_name_cluster(cluster: Cluster, class_deps: ClassDependencies) -> str:
    """Generate a fallback class name when LLM is unavailable.

    Uses the most common prefix/suffix among method names, or falls back to
    ``{OriginalClass}Extract{id}``.
    """
    methods = cluster.get_methods()
    if not methods:
        return f"{class_deps.class_name}Extract{cluster.id}"

    # Extract simple method names
    names = []
    for sig in methods:
        name = sig.split("(")[0].strip()
        if " " in name:
            name = name.split()[-1]
        names.append(name)

    # Find common prefix (e.g., "parse" in parseXml, parseJson, parseYaml → Parser)
    if len(names) >= 2:
        prefix = names[0]
        for n in names[1:]:
            while prefix and not n.startswith(prefix):
                prefix = prefix[:-1]
        if len(prefix) >= 3:
            name = prefix[0].upper() + prefix[1:] + "Operations"
            # Sanitize to valid Java identifier
            name = re.sub(r'[^a-zA-Z0-9_]', '', name)
            if not name or name[0].isdigit():
                name = 'Extracted' + name
            return name

    # Use the first method name as basis
    base = names[0]
    base = base[0].upper() + base[1:] if base else "Extracted"
    name = f"{base}Group"
    # Sanitize to valid Java identifier
    name = re.sub(r'[^a-zA-Z0-9_]', '', name)
    if not name or name[0].isdigit():
        name = 'Extracted' + name
    return name


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

        # Fallback: for clusters that LLM skipped, generate auto-named suggestions
        # so JDT code generation can still run
        named_cluster_ids = {s.cluster_id for s in suggestions}
        for cluster in ranked_clusters:
            if cluster.id not in named_cluster_ids:
                auto_name = _auto_name_cluster(cluster, class_deps)
                self.logger.info(
                    f"LLM skipped cluster {cluster.id}, using auto-name: {auto_name}"
                )
                fallback = RefactoringSuggestion(
                    cluster_id=cluster.id,
                    proposed_class_name=auto_name,
                    rationale="Auto-generated name (LLM unavailable or failed for this cluster)",
                    new_class_code="",
                    modified_original_code="",
                    cluster=cluster,
                    confidence_score=0.5,  # Lower confidence for auto-names
                )
                suggestions.append(fallback)

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

        if context.recorder:
            confidences = [s.confidence_score for s in suggestions if s.confidence_score is not None]
            context.recorder.end_stage("naming", {
                "suggestions_generated": len(suggestions),
                "avg_confidence": sum(confidences) / max(len(confidences), 1),
                "min_confidence": min(confidences) if confidences else 0,
                "max_confidence": max(confidences) if confidences else 0,
            })

        return True
