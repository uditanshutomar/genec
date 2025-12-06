"""Comparator for evaluating refactoring suggestions against ground truth."""

import json
from dataclasses import dataclass, field

import numpy as np
from scipy import stats

from genec.core.llm_interface import RefactoringSuggestion
from genec.evaluation.ground_truth_builder import ExtractClassRefactoring
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class EvaluationMetrics:
    """Evaluation metrics for refactoring suggestions."""

    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    matches: list[dict] = field(default_factory=list)


@dataclass
class ComparisonResult:
    """Result of comparing tool outputs against ground truth."""

    tool_name: str
    metrics: EvaluationMetrics
    quality_metrics: dict[str, float] = field(default_factory=dict)


class Comparator:
    """Compares refactoring suggestions against ground truth."""

    def __init__(self, jaccard_threshold: float = 0.8):
        """
        Initialize comparator.

        Args:
            jaccard_threshold: Minimum Jaccard similarity for a match
        """
        self.jaccard_threshold = jaccard_threshold
        self.logger = get_logger(self.__class__.__name__)

    def evaluate_suggestions(
        self,
        suggestions: list[RefactoringSuggestion],
        ground_truth: list[ExtractClassRefactoring],
        source_class: str,
    ) -> EvaluationMetrics:
        """
        Evaluate refactoring suggestions against ground truth.

        Args:
            suggestions: List of refactoring suggestions
            ground_truth: List of ground truth refactorings
            source_class: Source class name

        Returns:
            EvaluationMetrics
        """
        self.logger.info(
            f"Evaluating {len(suggestions)} suggestions against "
            f"{len(ground_truth)} ground truth refactorings"
        )

        # Filter ground truth to only this class
        relevant_gt = [gt for gt in ground_truth if source_class in gt.source_class]

        if not relevant_gt:
            self.logger.warning(f"No ground truth refactorings for {source_class}")

        metrics = EvaluationMetrics()

        # Match suggestions to ground truth
        matched_gt = set()

        for suggestion in suggestions:
            # Get extracted members from suggestion
            suggestion_members = set(suggestion.cluster.member_names)

            # Try to match with ground truth
            best_match = None
            best_similarity = 0.0

            for i, gt in enumerate(relevant_gt):
                if i in matched_gt:
                    continue

                gt_members = set(gt.extracted_members)

                # Calculate Jaccard similarity
                similarity = self._jaccard_similarity(suggestion_members, gt_members)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = i

            # Check if match is above threshold
            if best_match is not None and best_similarity >= self.jaccard_threshold:
                metrics.true_positives += 1
                matched_gt.add(best_match)

                metrics.matches.append(
                    {
                        "suggestion": suggestion.proposed_class_name,
                        "ground_truth": relevant_gt[best_match].extracted_class,
                        "similarity": best_similarity,
                    }
                )

                self.logger.debug(
                    f"Matched: {suggestion.proposed_class_name} -> "
                    f"{relevant_gt[best_match].extracted_class} "
                    f"(similarity: {best_similarity:.2f})"
                )
            else:
                metrics.false_positives += 1

        # Count false negatives (unmatched ground truth)
        metrics.false_negatives = len(relevant_gt) - len(matched_gt)

        # Calculate precision, recall, F1
        if metrics.true_positives + metrics.false_positives > 0:
            metrics.precision = metrics.true_positives / (
                metrics.true_positives + metrics.false_positives
            )
        else:
            metrics.precision = 0.0

        if metrics.true_positives + metrics.false_negatives > 0:
            metrics.recall = metrics.true_positives / (
                metrics.true_positives + metrics.false_negatives
            )
        else:
            metrics.recall = 0.0

        if metrics.precision + metrics.recall > 0:
            metrics.f1_score = (
                2 * (metrics.precision * metrics.recall) / (metrics.precision + metrics.recall)
            )
        else:
            metrics.f1_score = 0.0

        self.logger.info(
            f"Metrics - Precision: {metrics.precision:.3f}, "
            f"Recall: {metrics.recall:.3f}, "
            f"F1: {metrics.f1_score:.3f}"
        )

        return metrics

    def compare_approaches(
        self,
        results: dict[str, list[RefactoringSuggestion]],
        ground_truth: list[ExtractClassRefactoring],
        source_class: str,
    ) -> list[ComparisonResult]:
        """
        Compare multiple approaches against ground truth.

        Args:
            results: Dict mapping approach name to suggestions
            ground_truth: Ground truth refactorings
            source_class: Source class name

        Returns:
            List of ComparisonResult objects
        """
        comparisons = []

        for tool_name, suggestions in results.items():
            self.logger.info(f"Evaluating approach: {tool_name}")

            metrics = self.evaluate_suggestions(suggestions, ground_truth, source_class)

            comparison = ComparisonResult(tool_name=tool_name, metrics=metrics)

            comparisons.append(comparison)

        return comparisons

    def statistical_comparison(
        self,
        baseline_metrics: list[float],
        approach_metrics: list[float],
        metric_name: str = "F1-score",
    ) -> dict:
        """
        Perform statistical comparison between baseline and approach.

        Uses paired t-test.

        Args:
            baseline_metrics: Metrics from baseline approach
            approach_metrics: Metrics from evaluated approach
            metric_name: Name of the metric

        Returns:
            Dict with statistical test results
        """
        if len(baseline_metrics) != len(approach_metrics):
            self.logger.error("Metric lists must have same length")
            return {}

        if len(baseline_metrics) < 2:
            self.logger.warning("Not enough samples for statistical test")
            return {}

        # Paired t-test
        t_stat, p_value = stats.ttest_rel(approach_metrics, baseline_metrics)

        # Calculate effect size (Cohen's d)
        differences = np.array(approach_metrics) - np.array(baseline_metrics)
        cohen_d = np.mean(differences) / np.std(differences) if np.std(differences) > 0 else 0

        result = {
            "metric_name": metric_name,
            "baseline_mean": np.mean(baseline_metrics),
            "approach_mean": np.mean(approach_metrics),
            "difference": np.mean(differences),
            "t_statistic": t_stat,
            "p_value": p_value,
            "cohen_d": cohen_d,
            "significant": p_value < 0.05,
            "better": np.mean(approach_metrics) > np.mean(baseline_metrics),
        }

        self.logger.info(
            f"Statistical comparison ({metric_name}):\n"
            f"  Baseline mean: {result['baseline_mean']:.3f}\n"
            f"  Approach mean: {result['approach_mean']:.3f}\n"
            f"  p-value: {result['p_value']:.4f}\n"
            f"  Significant: {result['significant']}\n"
            f"  Effect size (Cohen's d): {result['cohen_d']:.3f}"
        )

        return result

    def _jaccard_similarity(self, set1: set, set2: set) -> float:
        """
        Calculate Jaccard similarity between two sets.

        Args:
            set1: First set
            set2: Second set

        Returns:
            Jaccard similarity (0.0 to 1.0)
        """
        if not set1 and not set2:
            return 1.0

        if not set1 or not set2:
            return 0.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def save_evaluation_report(self, comparisons: list[ComparisonResult], output_file: str):
        """
        Save evaluation report to JSON file.

        Args:
            comparisons: List of comparison results
            output_file: Output file path
        """
        report = {"approaches": []}

        for comparison in comparisons:
            approach_data = {
                "name": comparison.tool_name,
                "metrics": {
                    "precision": comparison.metrics.precision,
                    "recall": comparison.metrics.recall,
                    "f1_score": comparison.metrics.f1_score,
                    "true_positives": comparison.metrics.true_positives,
                    "false_positives": comparison.metrics.false_positives,
                    "false_negatives": comparison.metrics.false_negatives,
                },
                "quality_metrics": comparison.quality_metrics,
                "matches": comparison.metrics.matches,
            }
            report["approaches"].append(approach_data)

        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)

        self.logger.info(f"Saved evaluation report to {output_file}")

    def generate_summary_table(self, comparisons: list[ComparisonResult]) -> str:
        """
        Generate a formatted summary table.

        Args:
            comparisons: List of comparison results

        Returns:
            Formatted table string
        """
        lines = []
        lines.append("=" * 80)
        lines.append("EVALUATION SUMMARY")
        lines.append("=" * 80)
        lines.append(
            f"{'Approach':<20} {'Precision':>10} {'Recall':>10} {'F1-Score':>10} "
            f"{'TP':>5} {'FP':>5} {'FN':>5}"
        )
        lines.append("-" * 80)

        for comparison in comparisons:
            m = comparison.metrics
            lines.append(
                f"{comparison.tool_name:<20} "
                f"{m.precision:>10.3f} "
                f"{m.recall:>10.3f} "
                f"{m.f1_score:>10.3f} "
                f"{m.true_positives:>5} "
                f"{m.false_positives:>5} "
                f"{m.false_negatives:>5}"
            )

        lines.append("=" * 80)

        return "\n".join(lines)
