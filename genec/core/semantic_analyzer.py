"""Semantic analysis for extracting method features for clustering.

This module provides semantic feature extraction capabilities to complement
graph-based clustering with code complexity and size metrics.
"""

import re
from dataclasses import dataclass, field

import numpy as np
from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler

from genec.core.dependency_analyzer import ClassDependencies, MethodInfo
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class ComplexityMetrics:
    """Complexity metrics for a method."""

    cyclomatic_complexity: int = 1  # Number of decision points + 1
    cognitive_complexity: int = 0  # Weighted complexity (nesting depth matters)
    max_nesting_depth: int = 0


@dataclass
class SizeMetrics:
    """Size metrics for a method."""

    loc: int = 0  # Lines of code (total)
    sloc: int = 0  # Source lines of code (excluding comments/blanks)
    num_parameters: int = 0
    num_local_variables: int = 0
    num_statements: int = 0


@dataclass
class SignatureMetrics:
    """Method signature metrics."""

    num_parameters: int = 0
    has_return_value: bool = False
    is_void: bool = True
    has_exceptions: bool = False
    is_public: bool = True
    is_private: bool = False
    is_protected: bool = False
    is_static: bool = False


@dataclass
class CohesionMetrics:
    """Method cohesion metrics."""

    field_usage_count: int = 0  # Number of fields accessed
    method_call_count: int = 0  # Number of other methods called
    shared_field_ratio: float = 0.0  # Ratio of shared fields with other methods


@dataclass
class MethodFeatures:
    """Complete feature set for a method."""

    method_name: str
    complexity: ComplexityMetrics = field(default_factory=ComplexityMetrics)
    size: SizeMetrics = field(default_factory=SizeMetrics)
    signature: SignatureMetrics = field(default_factory=SignatureMetrics)
    cohesion: CohesionMetrics = field(default_factory=CohesionMetrics)

    def to_vector(self, feature_names: list[str] | None = None) -> np.ndarray:
        """Convert features to numpy vector for clustering."""
        if feature_names is None:
            feature_names = self.get_default_feature_names()

        vector = []
        for fname in feature_names:
            if fname == "complexity":
                vector.append(self.complexity.cyclomatic_complexity)
            elif fname == "cognitive_complexity":
                vector.append(self.complexity.cognitive_complexity)
            elif fname == "nesting_depth":
                vector.append(self.complexity.max_nesting_depth)
            elif fname == "loc":
                vector.append(self.size.loc)
            elif fname == "sloc":
                vector.append(self.size.sloc)
            elif fname == "parameters":
                vector.append(self.size.num_parameters)
            elif fname == "local_vars":
                vector.append(self.size.num_local_variables)
            elif fname == "statements":
                vector.append(self.size.num_statements)
            elif fname == "field_usage":
                vector.append(self.cohesion.field_usage_count)
            elif fname == "method_calls":
                vector.append(self.cohesion.method_call_count)
            elif fname == "shared_fields":
                vector.append(self.cohesion.shared_field_ratio)
            elif fname == "is_void":
                vector.append(1 if self.signature.is_void else 0)
            elif fname == "is_static":
                vector.append(1 if self.signature.is_static else 0)
            else:
                vector.append(0.0)

        return np.array(vector, dtype=float)

    @staticmethod
    def get_default_feature_names() -> list[str]:
        """Get default feature names for clustering."""
        return [
            "complexity",
            "cognitive_complexity",
            "nesting_depth",
            "loc",
            "sloc",
            "parameters",
            "field_usage",
            "method_calls",
        ]


class SemanticAnalyzer:
    """Analyzes code semantics to extract method features."""

    def __init__(self, feature_names: list[str] | None = None, normalization: str = "zscore"):
        """
        Initialize semantic analyzer.

        Args:
            feature_names: List of features to extract (None = all default features)
            normalization: Normalization method ('zscore', 'minmax', 'robust', 'none')
        """
        self.feature_names = feature_names or MethodFeatures.get_default_feature_names()
        self.normalization = normalization
        self.scaler = None
        self.logger = get_logger(self.__class__.__name__)

    def extract_class_features(self, class_deps: ClassDependencies) -> dict[str, MethodFeatures]:
        """
        Extract features for all methods in a class.

        Args:
            class_deps: Class dependencies

        Returns:
            Dictionary mapping method signature to features
        """
        features = {}

        all_methods = class_deps.get_all_methods()

        for method in all_methods:
            method_features = self.extract_method_features(method, class_deps)
            features[method.signature] = method_features

        self.logger.info(f"Extracted features for {len(features)} methods")

        return features

    def extract_method_features(
        self, method: MethodInfo, class_deps: ClassDependencies
    ) -> MethodFeatures:
        """
        Extract all features for a single method.

        Args:
            method: Method information
            class_deps: Class dependencies for cohesion metrics

        Returns:
            Complete feature set
        """
        features = MethodFeatures(method_name=method.name)

        # Complexity metrics
        features.complexity = self.calculate_complexity(method.body)

        # Size metrics
        features.size = self.calculate_size_metrics(method)

        # Signature metrics
        features.signature = self.extract_signature_metrics(method)

        # Cohesion metrics
        features.cohesion = self.calculate_cohesion_metrics(method, class_deps)

        return features

    def calculate_complexity(self, method_body: str) -> ComplexityMetrics:
        """
        Calculate complexity metrics for a method.

        Args:
            method_body: Method source code

        Returns:
            Complexity metrics
        """
        metrics = ComplexityMetrics()

        # Cyclomatic complexity: count decision points
        decision_keywords = [
            r"\bif\b",
            r"\belse\s+if\b",
            r"\bwhile\b",
            r"\bfor\b",
            r"\bcase\b",
            r"\bcatch\b",
            r"\b\?\s*",
            r"\b&&\b",
            r"\b\|\|\b",
        ]

        cyclomatic = 1  # Base complexity
        for keyword in decision_keywords:
            cyclomatic += len(re.findall(keyword, method_body))

        metrics.cyclomatic_complexity = cyclomatic

        # Cognitive complexity: weighted by nesting depth
        cognitive = 0
        nesting_depth = 0
        max_depth = 0

        for line in method_body.split("\n"):
            # Count opening braces
            open_braces = line.count("{")
            close_braces = line.count("}")

            # Update nesting
            nesting_depth += open_braces
            max_depth = max(max_depth, nesting_depth)
            nesting_depth -= close_braces

            # Decision points weighted by nesting
            for keyword in decision_keywords[:5]:  # Only control flow keywords
                if re.search(keyword, line):
                    cognitive += nesting_depth + 1

        metrics.cognitive_complexity = cognitive
        metrics.max_nesting_depth = max_depth

        return metrics

    def calculate_size_metrics(self, method: MethodInfo) -> SizeMetrics:
        """
        Calculate size metrics for a method.

        Args:
            method: Method information

        Returns:
            Size metrics
        """
        metrics = SizeMetrics()

        body = method.body
        lines = body.split("\n")

        # LOC: Total lines
        metrics.loc = len(lines)

        # SLOC: Non-empty, non-comment lines
        sloc = 0
        in_multiline_comment = False

        for line in lines:
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Handle multi-line comments
            if "/*" in stripped:
                in_multiline_comment = True
            if "*/" in stripped:
                in_multiline_comment = False
                continue
            if in_multiline_comment:
                continue

            # Skip single-line comments
            if stripped.startswith("//"):
                continue

            sloc += 1

        metrics.sloc = sloc

        # Parameters from signature
        metrics.num_parameters = len(method.parameters)

        # Local variables (approximation)
        # Count variable declarations
        var_patterns = [
            r"\b(int|long|short|byte|float|double|boolean|char)\s+(\w+)\s*[=;]",
            r"\b([A-Z]\w*)\s+(\w+)\s*[=;]",  # Object types
        ]

        local_vars = set()
        for pattern in var_patterns:
            matches = re.findall(pattern, body)
            for match in matches:
                if len(match) == 2:
                    local_vars.add(match[1])

        metrics.num_local_variables = len(local_vars)

        # Statements (approximation: count semicolons not in strings)
        # Simple heuristic
        metrics.num_statements = body.count(";")

        return metrics

    def extract_signature_metrics(self, method: MethodInfo) -> SignatureMetrics:
        """
        Extract method signature metrics.

        Args:
            method: Method information

        Returns:
            Signature metrics
        """
        metrics = SignatureMetrics()

        signature = method.signature

        # Parameters
        metrics.num_parameters = len(method.parameters)

        # Return type
        return_type = method.return_type if hasattr(method, "return_type") else "void"
        metrics.is_void = return_type == "void" or return_type is None
        metrics.has_return_value = not metrics.is_void

        # Exceptions
        metrics.has_exceptions = "throws" in signature

        # Access modifiers
        metrics.is_public = "public" in signature
        metrics.is_private = "private" in signature
        metrics.is_protected = "protected" in signature
        metrics.is_static = "static" in signature

        return metrics

    def calculate_cohesion_metrics(
        self, method: MethodInfo, class_deps: ClassDependencies
    ) -> CohesionMetrics:
        """
        Calculate cohesion metrics for a method.

        Args:
            method: Method information
            class_deps: Class dependencies

        Returns:
            Cohesion metrics
        """
        metrics = CohesionMetrics()

        # Field usage
        accessed_fields = class_deps.field_accesses.get(method.signature, [])
        metrics.field_usage_count = len(accessed_fields)

        # Method calls
        called_methods = class_deps.method_calls.get(method.signature, [])
        metrics.method_call_count = len(called_methods)

        # Shared field ratio
        if accessed_fields:
            # Count how many other methods share these fields
            total_sharing = 0
            for field in accessed_fields:
                # Count methods accessing this field
                methods_using_field = sum(
                    1
                    for m, fields in class_deps.field_accesses.items()
                    if field in fields and m != method.signature
                )
                total_sharing += methods_using_field

            metrics.shared_field_ratio = total_sharing / (
                len(accessed_fields) * max(1, len(class_deps.get_all_methods()) - 1)
            )

        return metrics

    def normalize_features(self, features_dict: dict[str, MethodFeatures]) -> np.ndarray:
        """
        Normalize feature vectors.

        Args:
            features_dict: Dictionary of method features

        Returns:
            Normalized feature matrix (n_methods x n_features)
        """
        if not features_dict:
            return np.array([])

        # Convert to matrix
        feature_matrix = np.array(
            [feat.to_vector(self.feature_names) for feat in features_dict.values()]
        )

        if self.normalization == "none":
            return feature_matrix

        # Create scaler
        if self.normalization == "zscore":
            self.scaler = StandardScaler()
        elif self.normalization == "minmax":
            self.scaler = MinMaxScaler()
        elif self.normalization == "robust":
            self.scaler = RobustScaler()
        else:
            self.logger.warning(f"Unknown normalization: {self.normalization}, using zscore")
            self.scaler = StandardScaler()

        # Fit and transform
        normalized = self.scaler.fit_transform(feature_matrix)

        self.logger.info(
            f"Normalized {normalized.shape[0]} methods with {normalized.shape[1]} features "
            f"using {self.normalization}"
        )

        return normalized

    def get_feature_importance(self, features_dict: dict[str, MethodFeatures]) -> dict[str, float]:
        """
        Calculate feature importance based on variance.

        Args:
            features_dict: Dictionary of method features

        Returns:
            Dictionary mapping feature names to importance scores
        """
        if not features_dict:
            return {}

        # Convert to matrix
        feature_matrix = np.array(
            [feat.to_vector(self.feature_names) for feat in features_dict.values()]
        )

        # Calculate variance for each feature
        variances = np.var(feature_matrix, axis=0)

        # Normalize to [0, 1]
        if variances.max() > 0:
            importance = variances / variances.max()
        else:
            importance = variances

        return {name: score for name, score in zip(self.feature_names, importance, strict=False)}
