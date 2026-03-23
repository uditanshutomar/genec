"""JDeodorant-style baseline: field-based agglomerative clustering."""

from genec.core.dependency_analyzer import ClassDependencies, DependencyAnalyzer
from genec.core.llm_interface import RefactoringSuggestion
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


class JDeodorantBaseline:
    """Baseline that groups methods by shared field access (agglomerative approach).

    Two methods are connected if they access the same field.  Transitive
    closure is used to merge connected components into clusters, which
    are then filtered by size.
    """

    def __init__(self, min_cluster_size: int = 3, max_cluster_size: int = 15):
        self.min_cluster_size = min_cluster_size
        self.max_cluster_size = max_cluster_size
        self.logger = get_logger(self.__class__.__name__)
        self.analyzer = DependencyAnalyzer()

    def analyze(self, class_file: str) -> list[RefactoringSuggestion]:
        """Parse a Java class and produce Extract Class suggestions via field-access clustering."""
        class_deps: ClassDependencies | None = self.analyzer.analyze_class(class_file)
        if class_deps is None:
            self.logger.error("Failed to analyse %s", class_file)
            return []

        clusters = self._build_field_clusters(class_deps)
        return self._clusters_to_suggestions(clusters, class_deps.class_name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_field_clusters(self, class_deps: ClassDependencies) -> list[dict]:
        """Group methods by shared field access using transitive closure.

        Returns a list of dicts: ``{"methods": set[str], "fields": set[str]}``.
        """
        all_methods = class_deps.get_all_methods()

        # Build field -> set of method signatures mapping
        field_to_methods: dict[str, set[str]] = {}
        method_to_fields: dict[str, set[str]] = {}

        for method in all_methods:
            accessed = set(class_deps.field_accesses.get(method.signature, []))
            method_to_fields[method.signature] = accessed
            for field_name in accessed:
                field_to_methods.setdefault(field_name, set()).add(method.signature)

        # Union-Find for transitive closure
        parent: dict[str, str] = {}

        def find(x: str) -> str:
            while parent.get(x, x) != x:
                parent[x] = parent.get(parent[x], parent[x])
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        # Connect methods that share a field
        for _field, methods in field_to_methods.items():
            method_list = list(methods)
            for i in range(len(method_list)):
                for j in range(i + 1, len(method_list)):
                    union(method_list[i], method_list[j])

        # Collect components
        components: dict[str, set[str]] = {}
        for method in all_methods:
            sig = method.signature
            if not method_to_fields.get(sig):
                continue  # skip methods that access no fields
            root = find(sig)
            components.setdefault(root, set()).add(sig)

        # Build clusters with their fields
        clusters: list[dict] = []
        for methods in components.values():
            fields: set[str] = set()
            for sig in methods:
                fields.update(method_to_fields.get(sig, set()))

            total_size = len(methods) + len(fields)
            if total_size < self.min_cluster_size or total_size > self.max_cluster_size:
                continue

            clusters.append({"methods": methods, "fields": fields})

        return clusters

    def _clusters_to_suggestions(
        self, clusters: list[dict], class_name: str
    ) -> list[RefactoringSuggestion]:
        """Convert raw clusters into RefactoringSuggestion objects."""
        suggestions: list[RefactoringSuggestion] = []
        for idx, cluster in enumerate(clusters):
            methods_list = sorted(cluster["methods"])
            fields_list = sorted(cluster["fields"])
            members = methods_list + fields_list

            proposed_name = f"{class_name}$Helper{idx + 1}"
            rationale = (
                f"Methods {', '.join(methods_list)} share access to "
                f"fields {', '.join(fields_list)}."
            )

            suggestion = RefactoringSuggestion(
                cluster_id=idx,
                proposed_class_name=proposed_name,
                rationale=rationale,
                new_class_code="",
                modified_original_code="",
                cluster=None,
            )
            suggestion.methods = members  # type: ignore[attr-defined]
            suggestions.append(suggestion)

        self.logger.info(
            "JDeodorant baseline produced %d suggestions", len(suggestions)
        )
        return suggestions
