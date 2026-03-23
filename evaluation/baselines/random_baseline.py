"""Random baseline: randomly partitions methods into groups."""

import random

from genec.core.dependency_analyzer import DependencyAnalyzer
from genec.core.llm_interface import RefactoringSuggestion
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


class RandomBaseline:
    """Baseline that randomly partitions class methods into groups."""

    def __init__(self, min_size: int = 3, max_size: int = 8, seed: int = 42):
        self.min_size = min_size
        self.max_size = max_size
        self.seed = seed
        self.logger = get_logger(self.__class__.__name__)
        self.analyzer = DependencyAnalyzer()

    def analyze(self, class_file: str) -> list[RefactoringSuggestion]:
        """Parse a Java class and randomly partition its methods."""
        class_deps = self.analyzer.analyze_class(class_file)
        if class_deps is None:
            self.logger.error("Failed to analyse %s", class_file)
            return []

        all_methods = class_deps.get_all_methods()
        signatures = [m.signature for m in all_methods]

        rng = random.Random(self.seed)
        rng.shuffle(signatures)

        groups: list[list[str]] = []
        i = 0
        while i < len(signatures):
            remaining = len(signatures) - i
            if remaining < self.min_size:
                # Not enough left for a full group; merge with the last group if one exists
                if groups:
                    groups[-1].extend(signatures[i:])
                break
            size = rng.randint(self.min_size, min(self.max_size, remaining))
            groups.append(signatures[i : i + size])
            i += size

        suggestions: list[RefactoringSuggestion] = []
        for idx, group in enumerate(groups):
            suggestion = RefactoringSuggestion(
                cluster_id=idx,
                proposed_class_name=f"RandomGroup{idx + 1}",
                rationale=f"Random partition of {len(group)} methods.",
                new_class_code="",
                modified_original_code="",
                cluster=None,
            )
            suggestion.methods = list(group)  # type: ignore[attr-defined]
            suggestions.append(suggestion)

        self.logger.info("Random baseline produced %d suggestions", len(suggestions))
        return suggestions
