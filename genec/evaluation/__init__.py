"""Evaluation framework modules."""

from genec.evaluation.comparator import Comparator
from genec.evaluation.ground_truth_builder import GroundTruthBuilder

# Note: Comparator is exported for external use (e.g., by evaluation scripts
# or notebooks) but is not currently consumed by any internal module.
# The evaluation/scripts/ directory performs comparisons inline instead.
__all__ = ["GroundTruthBuilder", "Comparator"]
