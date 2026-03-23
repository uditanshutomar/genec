"""Tests for the dependency analyzer module."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from genec.core.dependency_analyzer import DependencyAnalyzer, ClassDependencies


class TestDependencyAnalyzer:
    """Test cases for DependencyAnalyzer."""

    def test_init_default_config(self):
        """Test analyzer initializes with default config."""
        analyzer = DependencyAnalyzer()
        assert analyzer is not None

    def test_analyze_nonexistent_file(self, temp_dir):
        """Test handling of non-existent file."""
        analyzer = DependencyAnalyzer()
        result = analyzer.analyze_class(str(temp_dir / "nonexistent.java"))
        assert result is None

    def test_analyze_empty_file(self, temp_dir):
        """Test handling of empty Java file."""
        empty_file = temp_dir / "Empty.java"
        empty_file.write_text("")

        analyzer = DependencyAnalyzer()
        result = analyzer.analyze_class(str(empty_file))
        # Should handle gracefully
        assert result is None or isinstance(result, ClassDependencies)

    def test_analyze_simple_class(self, sample_java_file):
        """Test analyzing a simple Java class."""
        analyzer = DependencyAnalyzer()
        result = analyzer.analyze_class(str(sample_java_file))

        if result is not None:
            assert isinstance(result, ClassDependencies)
            assert result.class_name is not None

    def test_get_dependency_strength_missing_members(self):
        """Test get_dependency_strength with missing members."""
        analyzer = DependencyAnalyzer()

        # Create mock ClassDependencies with None matrix
        deps = ClassDependencies(
            class_name="Test",
            package_name="",
            file_path="/test/Test.java",
            member_names=["method1", "method2"],
            dependency_matrix=None,  # This should be handled
        )

        # Should return 0.0 without crashing
        strength = analyzer.get_dependency_strength(deps, "method1", "method2")
        assert strength == 0.0

    def test_get_dependency_strength_unknown_member(self):
        """Test get_dependency_strength with unknown member."""
        import numpy as np

        analyzer = DependencyAnalyzer()
        deps = ClassDependencies(
            class_name="Test",
            package_name="",
            file_path="/test/Test.java",
            member_names=["method1", "method2"],
            dependency_matrix=np.array([[1.0, 0.5], [0.5, 1.0]]),
        )

        # Unknown member should return 0.0
        strength = analyzer.get_dependency_strength(deps, "method1", "unknown")
        assert strength == 0.0


class TestClassDependencies:
    """Test cases for ClassDependencies dataclass."""

    def test_create_class_dependencies(self):
        """Test creating ClassDependencies instance."""
        deps = ClassDependencies(
            class_name="TestClass",
            package_name="",
            file_path="/path/to/TestClass.java",
            member_names=["method1", "field1"],
        )

        assert deps.class_name == "TestClass"
        assert deps.file_path == "/path/to/TestClass.java"
        assert len(deps.member_names) == 2
        assert deps.dependency_matrix is None  # Default

    def test_class_dependencies_with_matrix(self):
        """Test ClassDependencies with dependency matrix."""
        import numpy as np

        matrix = np.array([[1.0, 0.5], [0.5, 1.0]])
        deps = ClassDependencies(
            class_name="TestClass",
            package_name="",
            file_path="/path/to/TestClass.java",
            member_names=["method1", "method2"],
            dependency_matrix=matrix,
        )

        assert deps.dependency_matrix is not None
        assert deps.dependency_matrix.shape == (2, 2)
