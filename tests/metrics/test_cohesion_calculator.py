"""Tests for genec.metrics.cohesion_calculator.CohesionCalculator."""

import pytest

from genec.core.dependency_analyzer import ClassDependencies, MethodInfo, FieldInfo
from genec.metrics.cohesion_calculator import CohesionCalculator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _method(name: str, sig: str | None = None) -> MethodInfo:
    if sig is None:
        sig = f"{name}()"
    return MethodInfo(
        name=name,
        signature=sig,
        return_type="void",
        modifiers=["public"],
        parameters=[],
        start_line=1,
        end_line=10,
        body="",
    )


def _field(name: str, ftype: str = "int") -> FieldInfo:
    return FieldInfo(name=name, type=ftype, modifiers=["private"], line_number=1)


def _make_deps(
    methods: list[MethodInfo],
    fields: list[FieldInfo],
    field_accesses: dict[str, list[str]] | None = None,
    method_calls: dict[str, list[str]] | None = None,
) -> ClassDependencies:
    return ClassDependencies(
        class_name="TestClass",
        package_name="com.test",
        file_path="/tmp/TestClass.java",
        methods=methods,
        fields=fields,
        constructors=[],
        field_accesses=field_accesses or {},
        method_calls=method_calls or {},
    )


# ---------------------------------------------------------------------------
# TestLCOM5
# ---------------------------------------------------------------------------

class TestLCOM5:
    def test_perfectly_cohesive_class(self):
        """All methods access all fields -> LCOM5 = 0."""
        m1 = _method("getX")
        m2 = _method("getY")
        f1 = _field("x")
        f2 = _field("y")
        deps = _make_deps(
            methods=[m1, m2],
            fields=[f1, f2],
            field_accesses={
                "getX()": ["x", "y"],
                "getY()": ["x", "y"],
            },
        )

        calc = CohesionCalculator()
        lcom5 = calc.calculate_lcom5(deps)

        assert lcom5 == pytest.approx(0.0)

    def test_completely_incohesive_class(self):
        """Each method accesses exactly one distinct field -> LCOM5 = 1."""
        m1 = _method("getX")
        m2 = _method("getY")
        f1 = _field("x")
        f2 = _field("y")
        deps = _make_deps(
            methods=[m1, m2],
            fields=[f1, f2],
            field_accesses={
                "getX()": ["x"],
                "getY()": ["y"],
            },
        )

        calc = CohesionCalculator()
        lcom5 = calc.calculate_lcom5(deps)

        assert lcom5 == pytest.approx(1.0)

    def test_single_method_returns_zero(self):
        """Single method -> m <= 1, returns 0.0."""
        m1 = _method("only")
        f1 = _field("data")
        deps = _make_deps(
            methods=[m1],
            fields=[f1],
            field_accesses={"only()": ["data"]},
        )

        calc = CohesionCalculator()
        lcom5 = calc.calculate_lcom5(deps)

        assert lcom5 == pytest.approx(0.0)

    def test_no_fields_returns_zero(self):
        """No fields -> a == 0, returns 0.0."""
        m1 = _method("doA")
        m2 = _method("doB")
        deps = _make_deps(methods=[m1, m2], fields=[])

        calc = CohesionCalculator()
        lcom5 = calc.calculate_lcom5(deps)

        assert lcom5 == pytest.approx(0.0)

    def test_partial_cohesion(self):
        """Three methods, two fields, partial access -> LCOM5 between 0 and 1."""
        m1 = _method("a")
        m2 = _method("b")
        m3 = _method("c")
        f1 = _field("x")
        f2 = _field("y")
        # m1 accesses both, m2 accesses x only, m3 accesses y only
        # sum_mA = 2 (x accessed by m1,m2) + 2 (y accessed by m1,m3) = 4
        # LCOM5 = (3 - 4/2) / (3 - 1) = (3 - 2) / 2 = 0.5
        deps = _make_deps(
            methods=[m1, m2, m3],
            fields=[f1, f2],
            field_accesses={
                "a()": ["x", "y"],
                "b()": ["x"],
                "c()": ["y"],
            },
        )

        calc = CohesionCalculator()
        lcom5 = calc.calculate_lcom5(deps)

        assert lcom5 == pytest.approx(0.5)

    def test_no_methods_access_any_field(self):
        """Methods exist, fields exist, but no accesses -> LCOM5 = 1."""
        m1 = _method("a")
        m2 = _method("b")
        f1 = _field("x")
        deps = _make_deps(
            methods=[m1, m2],
            fields=[f1],
            field_accesses={},
        )

        calc = CohesionCalculator()
        lcom5 = calc.calculate_lcom5(deps)

        # sum_mA=0, LCOM5 = (2 - 0/1) / (2 - 1) = 2/1 = 2 => clamped to 1.0
        assert lcom5 == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# TestTCC
# ---------------------------------------------------------------------------

class TestTCC:
    def test_all_methods_connected(self):
        """All methods share a common field -> TCC = 1.0."""
        m1 = _method("a")
        m2 = _method("b")
        f1 = _field("shared")
        deps = _make_deps(
            methods=[m1, m2],
            fields=[f1],
            field_accesses={
                "a()": ["shared"],
                "b()": ["shared"],
            },
        )

        calc = CohesionCalculator()
        tcc = calc.calculate_tcc(deps)

        assert tcc == pytest.approx(1.0)

    def test_no_methods_connected(self):
        """No shared fields, no method calls -> TCC = 0.0."""
        m1 = _method("a")
        m2 = _method("b")
        f1 = _field("x")
        f2 = _field("y")
        deps = _make_deps(
            methods=[m1, m2],
            fields=[f1, f2],
            field_accesses={
                "a()": ["x"],
                "b()": ["y"],
            },
        )

        calc = CohesionCalculator()
        tcc = calc.calculate_tcc(deps)

        assert tcc == pytest.approx(0.0)

    def test_single_method_returns_zero(self):
        """Single method -> TCC = 0.0 (m <= 1)."""
        m1 = _method("only")
        deps = _make_deps(methods=[m1], fields=[])

        calc = CohesionCalculator()
        tcc = calc.calculate_tcc(deps)

        assert tcc == pytest.approx(0.0)

    def test_connected_via_method_call(self):
        """Methods connected through method calls should count as connected."""
        m1 = _method("caller")
        m2 = _method("callee")
        deps = _make_deps(
            methods=[m1, m2],
            fields=[],
            method_calls={"caller()": ["callee()"]},
        )

        calc = CohesionCalculator()
        tcc = calc.calculate_tcc(deps)

        assert tcc == pytest.approx(1.0)

    def test_partial_connectivity(self):
        """3 methods with 1 connected pair out of 3 possible -> TCC = 1/3."""
        m1 = _method("a")
        m2 = _method("b")
        m3 = _method("c")
        f1 = _field("shared")
        f2 = _field("lone")
        deps = _make_deps(
            methods=[m1, m2, m3],
            fields=[f1, f2],
            field_accesses={
                "a()": ["shared"],
                "b()": ["shared"],
                "c()": ["lone"],
            },
        )

        calc = CohesionCalculator()
        tcc = calc.calculate_tcc(deps)

        # Only a-b are connected (share "shared"), NP = 3
        assert tcc == pytest.approx(1.0 / 3.0)


# ---------------------------------------------------------------------------
# TestCohesionMetrics (combined)
# ---------------------------------------------------------------------------

class TestCohesionMetrics:
    def test_returns_both_metrics(self):
        """calculate_cohesion_metrics should return lcom5 and tcc."""
        m1 = _method("a")
        m2 = _method("b")
        f1 = _field("x")
        deps = _make_deps(
            methods=[m1, m2],
            fields=[f1],
            field_accesses={"a()": ["x"], "b()": ["x"]},
        )

        calc = CohesionCalculator()
        metrics = calc.calculate_cohesion_metrics(deps)

        assert "lcom5" in metrics
        assert "tcc" in metrics
        assert 0.0 <= metrics["lcom5"] <= 1.0
        assert 0.0 <= metrics["tcc"] <= 1.0
