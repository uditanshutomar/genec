"""Extended tests for DependencyAnalyzer and build_dependency_matrix."""

import numpy as np
import pytest

from genec.core.dependency_analyzer import (
    ClassDependencies,
    DependencyAnalyzer,
    FieldInfo,
    MethodInfo,
    WEIGHT_FIELD_ACCESS,
    WEIGHT_METHOD_CALL,
    WEIGHT_SHARED_FIELD,
    build_dependency_matrix,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _method(name, signature=None, body=""):
    return MethodInfo(
        name=name,
        signature=signature or f"{name}()",
        return_type="void",
        modifiers=["public"],
        parameters=[],
        start_line=1,
        end_line=10,
        body=body,
    )


def _field(name, ftype="int"):
    return FieldInfo(
        name=name,
        type=ftype,
        modifiers=["private"],
        line_number=1,
    )


def _make_deps(methods, fields, method_calls=None, field_accesses=None):
    """Create a ClassDependencies with given members and relationships."""
    deps = ClassDependencies(
        class_name="TestClass",
        package_name="com.example",
        file_path="/fake/TestClass.java",
        methods=methods,
        fields=fields,
        method_calls=method_calls or {},
        field_accesses=field_accesses or {},
    )
    return deps


class TestDependencyMatrix:
    """Tests for the build_dependency_matrix function."""

    def test_matrix_dimensions(self):
        """Matrix should have dimensions (methods+fields) x (methods+fields)."""
        deps = _make_deps(
            methods=[_method("alpha"), _method("beta")],
            fields=[_field("x")],
        )
        build_dependency_matrix(deps)

        assert deps.dependency_matrix.shape == (3, 3)
        assert len(deps.member_names) == 3

    def test_method_call_weight(self):
        """Method call should have weight WEIGHT_METHOD_CALL (1.0) in matrix."""
        m_alpha = _method("alpha")
        m_beta = _method("beta")

        deps = _make_deps(
            methods=[m_alpha, m_beta],
            fields=[],
            method_calls={m_alpha.signature: [m_beta.signature]},
        )
        build_dependency_matrix(deps)

        alpha_idx = deps.member_names.index(m_alpha.signature)
        beta_idx = deps.member_names.index(m_beta.signature)

        assert deps.dependency_matrix[alpha_idx][beta_idx] == pytest.approx(WEIGHT_METHOD_CALL)

    def test_field_access_weight(self):
        """Field access should have weight WEIGHT_FIELD_ACCESS (0.8) in matrix."""
        m_alpha = _method("alpha")
        f_x = _field("x")

        deps = _make_deps(
            methods=[m_alpha],
            fields=[f_x],
            field_accesses={m_alpha.signature: ["x"]},
        )
        build_dependency_matrix(deps)

        alpha_idx = deps.member_names.index(m_alpha.signature)
        x_idx = deps.member_names.index("x")

        assert deps.dependency_matrix[alpha_idx][x_idx] == pytest.approx(WEIGHT_FIELD_ACCESS)

    def test_matrix_symmetry_for_shared_fields(self):
        """Dependency matrix should be symmetric for shared fields."""
        m_alpha = _method("alpha")
        m_beta = _method("beta")
        f_x = _field("x")

        # Both alpha and beta access field x -> shared field coupling
        deps = _make_deps(
            methods=[m_alpha, m_beta],
            fields=[f_x],
            field_accesses={
                m_alpha.signature: ["x"],
                m_beta.signature: ["x"],
            },
        )
        build_dependency_matrix(deps)

        alpha_idx = deps.member_names.index(m_alpha.signature)
        beta_idx = deps.member_names.index(m_beta.signature)

        # Shared field creates symmetric coupling
        assert deps.dependency_matrix[alpha_idx][beta_idx] == pytest.approx(WEIGHT_SHARED_FIELD)
        assert deps.dependency_matrix[beta_idx][alpha_idx] == pytest.approx(WEIGHT_SHARED_FIELD)

    def test_no_self_loops_by_default(self):
        """Diagonal should be zero (no self-dependency) when there are no self-calls."""
        m = _method("alpha")
        deps = _make_deps(methods=[m], fields=[])
        build_dependency_matrix(deps)

        assert deps.dependency_matrix[0][0] == 0.0

    def test_empty_class(self):
        """Matrix should be 0x0 for a class with no members."""
        deps = _make_deps(methods=[], fields=[])
        build_dependency_matrix(deps)

        assert deps.dependency_matrix.shape == (0, 0)
        assert deps.member_names == []

    def test_fields_only(self):
        """Class with only fields should produce an empty method region."""
        deps = _make_deps(
            methods=[],
            fields=[_field("x"), _field("y")],
        )
        build_dependency_matrix(deps)

        # 2 fields, no methods
        assert deps.dependency_matrix.shape == (2, 2)
        # No coupling between fields directly (no methods to create shared access)
        assert np.allclose(deps.dependency_matrix, 0.0)

    def test_method_call_by_name_resolution(self):
        """When called method is specified by name (no parens), should still resolve."""
        m_alpha = _method("alpha")
        m_beta = _method("beta")

        deps = _make_deps(
            methods=[m_alpha, m_beta],
            fields=[],
            # Call using just the name without full signature
            method_calls={m_alpha.signature: ["beta"]},
        )
        build_dependency_matrix(deps)

        alpha_idx = deps.member_names.index(m_alpha.signature)
        beta_idx = deps.member_names.index(m_beta.signature)

        assert deps.dependency_matrix[alpha_idx][beta_idx] == pytest.approx(WEIGHT_METHOD_CALL)

    def test_overloaded_methods_get_reduced_weight(self):
        """Overloaded methods (same name, different signatures) get 0.9 * WEIGHT_METHOD_CALL."""
        m_caller = _method("caller")
        m_process_a = _method("process", signature="process(int)")
        m_process_b = _method("process", signature="process(String)")

        deps = _make_deps(
            methods=[m_caller, m_process_a, m_process_b],
            fields=[],
            # Call "process" by name -- ambiguous (2 overloads)
            method_calls={m_caller.signature: ["process"]},
        )
        build_dependency_matrix(deps)

        caller_idx = deps.member_names.index(m_caller.signature)
        pa_idx = deps.member_names.index(m_process_a.signature)
        pb_idx = deps.member_names.index(m_process_b.signature)

        expected = WEIGHT_METHOD_CALL * 0.2  # Low weight: can't determine which overload is called
        assert deps.dependency_matrix[caller_idx][pa_idx] == pytest.approx(expected)
        assert deps.dependency_matrix[caller_idx][pb_idx] == pytest.approx(expected)

    def test_multiple_shared_fields(self):
        """Multiple shared fields should keep the max weight between two methods."""
        m_alpha = _method("alpha")
        m_beta = _method("beta")
        f_x = _field("x")
        f_y = _field("y")

        deps = _make_deps(
            methods=[m_alpha, m_beta],
            fields=[f_x, f_y],
            field_accesses={
                m_alpha.signature: ["x", "y"],
                m_beta.signature: ["x", "y"],
            },
        )
        build_dependency_matrix(deps)

        alpha_idx = deps.member_names.index(m_alpha.signature)
        beta_idx = deps.member_names.index(m_beta.signature)

        # max() is used, so weight should be WEIGHT_SHARED_FIELD regardless of how many shared fields
        assert deps.dependency_matrix[alpha_idx][beta_idx] == pytest.approx(WEIGHT_SHARED_FIELD)

    def test_custom_weights(self):
        """build_dependency_matrix should accept custom weight overrides."""
        m_alpha = _method("alpha")
        m_beta = _method("beta")

        deps = _make_deps(
            methods=[m_alpha, m_beta],
            fields=[],
            method_calls={m_alpha.signature: [m_beta.signature]},
        )
        build_dependency_matrix(deps, weight_method_call=2.5)

        alpha_idx = deps.member_names.index(m_alpha.signature)
        beta_idx = deps.member_names.index(m_beta.signature)

        assert deps.dependency_matrix[alpha_idx][beta_idx] == pytest.approx(2.5)


class TestDependencyAnalyzerGetStrength:
    """Tests for DependencyAnalyzer.get_dependency_strength()."""

    def test_returns_correct_weight(self):
        m_a = _method("a")
        m_b = _method("b")

        deps = _make_deps(
            methods=[m_a, m_b],
            fields=[],
            method_calls={m_a.signature: [m_b.signature]},
        )
        build_dependency_matrix(deps)

        analyzer = DependencyAnalyzer()
        strength = analyzer.get_dependency_strength(deps, m_a.signature, m_b.signature)
        assert strength == pytest.approx(WEIGHT_METHOD_CALL)

    def test_returns_zero_for_no_dependency(self):
        m_a = _method("a")
        m_b = _method("b")

        deps = _make_deps(methods=[m_a, m_b], fields=[])
        build_dependency_matrix(deps)

        analyzer = DependencyAnalyzer()
        strength = analyzer.get_dependency_strength(deps, m_a.signature, m_b.signature)
        assert strength == 0.0

    def test_returns_zero_for_unknown_member(self):
        deps = _make_deps(methods=[_method("a")], fields=[])
        build_dependency_matrix(deps)

        analyzer = DependencyAnalyzer()
        strength = analyzer.get_dependency_strength(deps, "a()", "nonExistent()")
        assert strength == 0.0

    def test_returns_zero_when_no_matrix(self):
        deps = _make_deps(methods=[], fields=[])
        # Don't build matrix -- it should be None
        analyzer = DependencyAnalyzer()
        strength = analyzer.get_dependency_strength(deps, "a()", "b()")
        assert strength == 0.0


class TestModuleLevelConstants:
    """Verify the module-level weight constants match expected values."""

    def test_weight_method_call(self):
        assert WEIGHT_METHOD_CALL == 1.0

    def test_weight_field_access(self):
        assert WEIGHT_FIELD_ACCESS == 0.8

    def test_weight_shared_field(self):
        assert WEIGHT_SHARED_FIELD == 0.9

    def test_module_level_constants_accessible(self):
        """Module-level weight constants should be importable and correct."""
        assert WEIGHT_METHOD_CALL == 1.0
        assert WEIGHT_FIELD_ACCESS == 0.8
        assert WEIGHT_SHARED_FIELD == 0.9
