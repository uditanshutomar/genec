"""Backward-compatibility shim — see field_sharing_baseline.py."""

from evaluation.baselines.field_sharing_baseline import FieldSharingBaseline

# Backward-compatible alias
JDeodorantBaseline = FieldSharingBaseline

__all__ = ["FieldSharingBaseline", "JDeodorantBaseline"]
