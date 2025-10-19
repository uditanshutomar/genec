"""Cohesion metrics calculator (LCOM5)."""

import numpy as np
from typing import Dict, Set

from genec.core.dependency_analyzer import ClassDependencies
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


class CohesionCalculator:
    """Calculates cohesion metrics for Java classes."""

    def __init__(self):
        """Initialize cohesion calculator."""
        self.logger = get_logger(self.__class__.__name__)

    def calculate_lcom5(self, class_deps: ClassDependencies) -> float:
        """
        Calculate LCOM5 (Lack of Cohesion of Methods 5).

        LCOM5 measures the lack of cohesion in a class based on field usage.

        Formula:
        LCOM5 = (m - sum(mA)/a) / (m - 1)

        Where:
        - m = number of methods
        - a = number of fields
        - mA = number of methods accessing each field

        Range: [0, 1]
        - 0 = perfect cohesion (all methods access all fields)
        - 1 = no cohesion (each method accesses different fields)

        Args:
            class_deps: ClassDependencies object

        Returns:
            LCOM5 value (0.0 to 1.0, or 0.0 if not applicable)
        """
        methods = class_deps.get_all_methods()
        fields = class_deps.fields

        m = len(methods)
        a = len(fields)

        # Edge cases
        if m <= 1 or a == 0:
            self.logger.debug("LCOM5 not applicable (too few methods or no fields)")
            return 0.0

        # Count how many methods access each field
        field_access_counts = {}
        for field in fields:
            count = 0
            for method in methods:
                accessed_fields = class_deps.field_accesses.get(method.signature, [])
                if field.name in accessed_fields:
                    count += 1
            field_access_counts[field.name] = count

        # Calculate sum(mA)
        sum_mA = sum(field_access_counts.values())

        # Calculate LCOM5
        lcom5 = (m - sum_mA / a) / (m - 1)

        # Clamp to [0, 1]
        lcom5 = max(0.0, min(1.0, lcom5))

        self.logger.debug(f"LCOM5 = {lcom5:.4f} (m={m}, a={a}, sum_mA={sum_mA})")

        return lcom5

    def calculate_tcc(self, class_deps: ClassDependencies) -> float:
        """
        Calculate TCC (Tight Class Cohesion).

        TCC measures the ratio of directly connected methods to the maximum
        possible connections.

        Formula:
        TCC = NDC / NP

        Where:
        - NDC = number of directly connected method pairs
        - NP = maximum possible connections = m * (m - 1) / 2

        Two methods are directly connected if they access the same field
        or one calls the other.

        Args:
            class_deps: ClassDependencies object

        Returns:
            TCC value (0.0 to 1.0)
        """
        methods = class_deps.get_all_methods()
        m = len(methods)

        if m <= 1:
            return 0.0

        # Maximum possible connections
        NP = m * (m - 1) // 2

        # Count directly connected pairs
        NDC = 0

        for i in range(m):
            for j in range(i + 1, m):
                method1 = methods[i]
                method2 = methods[j]

                if self._are_methods_connected(method1, method2, class_deps):
                    NDC += 1

        tcc = NDC / NP if NP > 0 else 0.0

        self.logger.debug(f"TCC = {tcc:.4f} (NDC={NDC}, NP={NP})")

        return tcc

    def _are_methods_connected(
        self,
        method1,
        method2,
        class_deps: ClassDependencies
    ) -> bool:
        """
        Check if two methods are directly connected.

        Methods are connected if:
        1. They access a common field, or
        2. One calls the other

        Args:
            method1: First method
            method2: Second method
            class_deps: ClassDependencies

        Returns:
            True if methods are connected
        """
        # Check if they access common fields
        fields1 = set(class_deps.field_accesses.get(method1.signature, []))
        fields2 = set(class_deps.field_accesses.get(method2.signature, []))

        if fields1 & fields2:  # Intersection
            return True

        # Check if one calls the other
        calls1 = class_deps.method_calls.get(method1.signature, [])
        calls2 = class_deps.method_calls.get(method2.signature, [])

        if method2.name in calls1 or method1.name in calls2:
            return True

        return False

    def calculate_cohesion_metrics(self, class_deps: ClassDependencies) -> Dict[str, float]:
        """
        Calculate all cohesion metrics.

        Args:
            class_deps: ClassDependencies object

        Returns:
            Dictionary of metric names to values
        """
        metrics = {
            'lcom5': self.calculate_lcom5(class_deps),
            'tcc': self.calculate_tcc(class_deps)
        }

        return metrics
